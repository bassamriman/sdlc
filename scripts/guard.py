#!/usr/bin/env python3
"""PreToolUse(Bash): commit only after a green check on this exact tree; ask before push, PR creation or merge, and branch delete (local or remote); deny bare force-push.

The commit gate fails closed: a crash exits 2, and hooks.json sets onFailure=block for timeouts."""
from __future__ import annotations

import json
import os
import re
import sys

import gates
import state as st

VALUE = r"""(?:[^\s"']+|"[^"]*"|'[^']*')+"""
GIT = rf"\bgit\b(?:\s+(?:-C|-c|--git-dir|--work-tree)\s+{VALUE}|\s+-\S+)*\s+"
COMMIT = re.compile(GIT + r"commit(?![\w-])")
PUSH = re.compile(GIT + r"push\b(?P<rest>[^|&;]*)")
BRANCH_DELETE = re.compile(GIT + r"branch\b[^|&;]*\s(-d|-D|--delete)\b")
REMOTE_DELETE = re.compile(r"(^|\s)(--delete|-d|:\S+)(\s|$)")
PR_ACTION = re.compile(r"\bgh\s+pr\s+(create|merge)\b")
FORCE = re.compile(r"(^|\s)(--force|-[a-zA-Z]*f[a-zA-Z]*|\+\S+)(\s|$)")
RELEVANT = re.compile(r"\b(git|gh)\b")


MODE: list = [None]  # the session's permission mode, from the hook event


def decide(wanted: str, text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": gates.decision(MODE[0], wanted),
                                             "permissionDecisionReason": gates.reason(MODE[0], wanted, text)}}))


def gate_open(cwd: str | None) -> bool:
    """True only in a repo never initialised (no .sdlc/) or when the tree equals the last green check."""
    sdlc = st.root(cwd) / ".sdlc"
    if not sdlc.exists():
        return True
    if not (sdlc / "stack.json").exists():
        raise RuntimeError("no .sdlc/stack.json: run /sdlc:init")  # an initialised repo without its stack is a closed gate
    return st.load(cwd).get("checked_hash") == st.tree_hash(cwd)


def diagram_missing(cwd: str | None) -> bool:
    """With gates.diagram=require: a commit that touches source must also carry an updated docs/arch/ diagram (archdiff.py)."""
    if gates.current()["diagram"] != "require":
        return False
    changed = st.changed_paths(st.root(cwd))
    touches_code = any(p.rsplit(".", 1)[-1] in ("py", "ts", "tsx", "js", "jsx", "java", "scala", "kt", "go", "rs") for p in changed)
    return touches_code and not any(p.startswith("docs/arch/") for p in changed)


def commit_blocked(command: str, cwd: str | None) -> bool:
    if not COMMIT.search(command) or gates.current()["commit"] == "off":
        return False
    if diagram_missing(cwd):
        print("sdlc: this epic requires an architecture diagram of the diff in every commit. Run archdiff.py, git add docs/arch/, then commit.", file=sys.stderr)
        return True
    try:
        return not gate_open(cwd)
    except Exception as exc:  # fail closed: an unreadable repo must not let a commit through
        print(f"sdlc: commit gate could not run ({exc}); fix the repo or set SDLC_GATE=off", file=sys.stderr)
        return True


def confirmations(command: str) -> None:
    """Human gates per SDLC_GATES; the bare force-push denial never relaxes."""
    gate = gates.current()
    push = PUSH.search(command)
    rest = re.sub(r"(^|\s)--force-with-lease(=\S*)?(?=\s|$)", " ", push.group("rest")) if push else ""
    if push and FORCE.search(rest):
        decide("deny", "sdlc: bare force-push denied; use --force-with-lease")
    elif push and REMOTE_DELETE.search(push.group("rest")) and gate["branch_delete"] == "ask":
        decide("ask", "sdlc: confirm remote branch delete")
    elif push and gate["push"] == "ask":
        decide("ask", "sdlc: confirm push")
    elif PR_ACTION.search(command) and gate["pr"] == "ask":
        decide("ask", "sdlc: confirm PR action (gh may push the branch first)")
    elif BRANCH_DELETE.search(command) and gate["branch_delete"] == "ask":
        decide("ask", "sdlc: confirm branch delete")


def _main() -> int:
    event = json.load(sys.stdin)
    MODE[0] = event.get("permission_mode")
    command = event.get("tool_input", {}).get("command", "")
    if os.environ.get("SDLC_GATE") == "off" or not RELEVANT.search(command):
        return 0
    if commit_blocked(command, event.get("cwd")):
        print("sdlc: tree changed since the last green check. Run /sdlc:check, then commit.", file=sys.stderr)
        return 2
    confirmations(command)
    return 0


def main() -> int:
    try:
        return _main()
    except Exception as exc:  # a crash must block, not rely on the host's onFailure
        print(f"sdlc: guard could not run ({exc}); set SDLC_GATE=off to bypass", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
