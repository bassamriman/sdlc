#!/usr/bin/env python3
"""PreToolUse in a fleet agent (SDLC_AGENT_WORKSPACE set): deny edits outside the workspace, ask before any outbound message,
ask before a Bash command that writes or runs git state changes against a path outside the workspace. Inert otherwise."""
from __future__ import annotations

import json
import os
import re
import sys

import gates

PLUGIN = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)) + os.sep
SYSTEM = ("/usr/", "/bin/", "/sbin/", "/opt/", "/dev/", "/tmp/", "/private/tmp/", PLUGIN)  # Bash may name these; file tools never
PATHS = re.compile(r"(?<![\w.-])(/[\w./@+-]+)(?![\w:])")  # not a /slash:command, not mid-word
RELATIVE = re.compile(r"(?<![\w/.$-])((?:~|\.\.?|\$\{?\w+\}?)(?:/[\w.@+$-]+)*/?)(?![\w:])")
WRITES = re.compile(r"\d?>>?|&>"
                    r"|(^|[\s;&|(])(tee|cp|mv|rm|rsync|install|ln|mkdir|touch|truncate|chmod|chown|sed\s+-i|perl\s+-p?i|(python[0-9.]*|node|perl|ruby)\s+-[ce])(?=\s|$)"
                    r"|\bdd\b[^;&|]*\bof="
                    r"|\bgit\s+((-C\s+\S+|--git-dir=\S+|--work-tree=\S+)\s+)*(merge|checkout|switch|reset|rebase|commit|apply|am|cherry-pick|push|branch|worktree)\b")
OVERRIDES = re.compile(r"(^|[\s;&|(])((env\s+(-\S+\s+)*)?SDLC_[A-Z_]+=|(export|unset)\s+SDLC_[A-Z_]+)")  # identity and gates come from the launcher, never the command line
PROTECTED = re.compile(r"/(\.claude/settings(\.local)?\.json|\.git(/|$))")  # these files carry the isolation itself


MODE: list = [None]  # the session's permission mode, from the hook event


def decide(wanted: str, text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": gates.decision(MODE[0], wanted),
                                             "permissionDecisionReason": gates.reason(MODE[0], wanted, text)}}))


def inside(path: str, allowed: list[str], *, system_ok: bool = False) -> bool:
    real = os.path.realpath(path)
    return any(real.startswith(prefix) for prefix in allowed) or (system_ok and real.startswith(SYSTEM))


def real_place(path: str) -> bool:
    """A path worth judging: it exists, or its parent does (a file about to be created)."""
    return os.path.exists(path) or os.path.isdir(os.path.dirname(path.rstrip("/")) or "/") and path.count("/") > 1


SEGMENT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")
REDIRECT = re.compile(r"(?<![<&\d])(?:\d|&)?>>?(?![>&])\s*([^\s;&|<>()]+)")  # a file target; `2>&1` duplicates a stream and is none
VERB = re.compile(r"^(?:\w+=\S*\s+)*(?:sudo\s+)?(tee|cp|mv|rm|rsync|install|ln|mkdir|touch|truncate|chmod|chown|sed\s+-i|perl\s+-p?i|(?:python[0-9.]*|node|perl|ruby)\s+-[ce])\b")
DD_OUT = re.compile(r"\bdd\b.*?\bof=(\S+)")
GIT_WRITE = re.compile(r"\bgit\s+((?:(?:-C\s+\S+|--git-dir=\S+|--work-tree=\S+)\s+)*)(?:merge|checkout|switch|reset|rebase|commit|apply|am|cherry-pick|push|branch|worktree)\b")
GIT_PLACE = re.compile(r"-C\s+(\S+)|--git-dir=(\S+)|--work-tree=(\S+)")


def resolve(token: str, cwd: str) -> str:
    token = os.path.expandvars(os.path.expanduser(token.strip("'\"")))
    return token if token.startswith("/") or "$" in token else os.path.join(cwd, token)


def segment_paths(segment: str, cwd: str) -> list[str]:
    found = list(PATHS.findall(segment)) + [resolve(t, cwd) for t in RELATIVE.findall(segment)]
    return [p if p.startswith("/") or "$" in p else os.path.join(cwd, p) for p in found]


def segment_targets(segment: str, cwd: str) -> list[str]:
    """What one command segment writes: redirect files, every path given to a write verb, dd's output, a git write's repository."""
    targets = [resolve(t, cwd) for t in REDIRECT.findall(segment)]
    bare = REDIRECT.sub(" ", segment)
    if VERB.search(bare):
        targets += segment_paths(bare, cwd)
    targets += [resolve(t, cwd) for t in DD_OUT.findall(segment)]
    git = GIT_WRITE.search(segment)
    if git:
        places = [next(p for p in m if p) for m in GIT_PLACE.findall(git.group(1))]
        targets += [resolve(p, cwd) for p in places] or [cwd]
    return targets


def write_targets(command: str, cwd: str) -> list[str]:
    """Every path the command writes, segment by segment, following `cd` so relative targets resolve where they land."""
    targets = []
    for segment in SEGMENT.split(command):
        cd = re.match(r"^cd\s+(\S+)\s*$", segment.strip())
        if cd:
            cwd = resolve(cd.group(1), cwd)
            continue
        targets += segment_targets(segment, cwd)
    return targets


def message_decision(tool_input: dict) -> None:
    peer = str(tool_input.get("to", "")).startswith(f"sdlc/{os.environ.get('SDLC_EPIC', '')}/")
    if not (peer and gates.current()["message"] == "auto"):
        decide("ask", "sdlc fleet: confirm outbound message")


def bash_decision(tool_input: dict, allowed: list[str], cwd: str) -> None:
    command = tool_input.get("command", "")
    if OVERRIDES.search(command):
        return decide("deny", "sdlc fleet: command sets or unsets an SDLC_* variable; run it without the prefix")
    targets = [t for t in write_targets(command, cwd) if "$" in t or real_place(t)]
    protected = next((t for t in targets if "$" not in t and PROTECTED.search(os.path.realpath(t))), None)
    if protected:
        return decide("deny", f"sdlc fleet: command writes a protected file (.claude/settings*.json or .git/): {protected}")
    plugin = next((t for t in targets if "$" not in t and os.path.realpath(t).startswith(PLUGIN)), None)
    if plugin:
        return decide("deny", f"sdlc fleet: write into the plugin denied: {plugin}")
    strays = [t for t in targets if not inside(t, allowed, system_ok=True)]
    if strays:
        return decide("ask", f"sdlc fleet: command writes or changes git state outside the workspace: {strays[0]}")
    shell_process_gate(targets)


def shell_process_gate(targets: list[str]) -> None:
    """Writes through the shell meet the same rule as edits: no source change before /sdlc:init and /sdlc:plan."""
    workspace = os.environ.get("SDLC_AGENT_WORKSPACE", "")
    missing = next((m for t in targets if "$" not in t for m in [process_gap(t, workspace)] if m), None)
    if missing:
        decide("deny", f"sdlc fleet: no source edits before {missing}, through the shell either; run it first")


def edit_decision(tool_input: dict, allowed: list[str], workspace: str) -> int:
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if target and (not inside(target, allowed) or PROTECTED.search(os.path.realpath(target))):
        print(f"sdlc fleet: write outside workspace {workspace} or to a protected file denied: {target}", file=sys.stderr)
        return 2
    missing = process_gap(target or "", workspace)
    if missing:
        print(f"sdlc fleet: no source edits before {missing}; run it first (a change under about 20 lines still gets a one-slice plan)", file=sys.stderr)
        return 2
    return 0


def repo_of(path: str, home: str) -> str:
    """The folder whose .sdlc governs the path: the nearest one that has .sdlc (so a submodule or nested repo inside the
    clone is still governed by the clone), else the nearest git repository, else the workspace itself."""
    chain, here = [], path if os.path.isdir(path) else os.path.dirname(path)
    while here.startswith(home) and here != os.path.dirname(here):
        chain.append(here)
        here = os.path.dirname(here)
    chain.append(home)
    with_sdlc = next((d for d in chain if os.path.isdir(os.path.join(d, ".sdlc"))), None)
    return with_sdlc or next((d for d in chain if os.path.exists(os.path.join(d, ".git"))), home)


def process_gap(target: str, workspace: str) -> str | None:
    """An agent edits source only after /sdlc:init and /sdlc:plan; .sdlc/ itself and the orchestrator are exempt."""
    real, home = os.path.realpath(target), os.path.realpath(workspace)
    if os.environ.get("SDLC_AGENT_NAME") == "orchestrator" or not real.startswith(home + os.sep) or "/.sdlc/" in real + "/":
        return None
    if os.path.isdir(real):
        return None  # a folder is a git operation's repository (rebase, merge, checkout), not a source edit
    sdlc = os.path.join(repo_of(real, home), ".sdlc")  # the clone sits one level below the agent's workspace
    if not os.path.exists(os.path.join(sdlc, "stack.json")):
        return "/sdlc:init"
    return None if os.path.exists(os.path.join(sdlc, "plan.md")) else "/sdlc:plan"


def writable(workspace: str, event: dict) -> list[str]:
    """The workspace and the session scratchpad; for the orchestrator also resources/, which is its to write."""
    root = os.environ.get("SDLC_FLEET_ROOT")
    shared = os.path.join(root, "resources") if root and os.environ.get("SDLC_AGENT_NAME") == "orchestrator" else None
    job = os.environ.get("CLAUDE_JOB_DIR")  # the session's own temp folder
    return [os.path.realpath(p) + os.sep for p in (workspace, event.get("scratchpad_dir"), shared, job) if p]


def _main() -> int:
    workspace = os.environ.get("SDLC_AGENT_WORKSPACE")
    if not workspace:
        return 0
    event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    MODE[0] = event.get("permission_mode")
    tool, tool_input, allowed = event.get("tool_name"), event.get("tool_input", {}), writable(workspace, event)
    if tool == "SendMessage":
        message_decision(tool_input)
    elif tool == "Bash":
        bash_decision(tool_input, allowed, event.get("cwd") or workspace)
    else:
        return edit_decision(tool_input, allowed, workspace)
    return 0


def main() -> int:
    try:
        return _main()
    except Exception as exc:  # a crash must block, not rely on the host's onFailure
        print(f"sdlc: isolation hook could not run ({exc})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
