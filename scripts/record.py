#!/usr/bin/env python3
"""Opt-in, local-only usage log. Hook: reads one event on stdin. CLI: `on|off|status`, `feedback <text> [about]`. Always exits 0."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shlex
import sys
from pathlib import Path

TRIVIAL = {"ls", "cat", "echo", "cd", "pwd", "head", "tail", "wc", "true", "false", "which", "env", "printenv"}
INTENT_MAX, ARGS_MAX, TEXT_MAX = 280, 160, 2000


def data_dir() -> Path:
    """One place for the marker and the logs, whoever runs: hooks (which get CLAUDE_PLUGIN_DATA), the Bash tool and the shell (which do not)."""
    return Path(os.environ.get("SDLC_DATA_DIR") or Path.home() / ".local/share/sdlc")


def enabled() -> bool:
    return (data_dir() / "telemetry.on").exists()


def version() -> str:
    try:
        return json.loads((Path(__file__).resolve().parent.parent / ".claude-plugin/plugin.json").read_text()).get("version", "?")
    except (OSError, ValueError):
        return "?"


def append(record: dict, log: str = "usage") -> None:
    if log == "usage" and not enabled():
        return
    stamped = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "v": version(), **record}
    data_dir().mkdir(parents=True, exist_ok=True)
    with (data_dir() / f"{log}.jsonl").open("a") as f:
        f.write(json.dumps(stamped) + "\n")


def signature(command: str) -> str | None:
    segment = command.split("&&")[0].split("||")[0].split(";")[0].split("|")[0]
    try:
        tokens = [t for t in shlex.split(segment) if "=" not in t or t.startswith("-")]
    except ValueError:
        return None
    if not tokens or os.path.basename(tokens[0]) in TRIVIAL:
        return None
    binary = os.path.basename(tokens[0])
    sub = next((t for t in tokens[1:] if not t.startswith(("-", "/", ".", "~"))), "")
    return f"{binary} {sub}".strip()


def outcome(event: dict) -> bool | None:
    response = event.get("tool_response")
    if not isinstance(response, dict):
        return None
    for key in ("exitCode", "exit_code", "returncode"):
        if key in response:
            return response[key] == 0
    return not (response.get("is_error") or response.get("interrupted"))


TYPED_SKILL = re.compile(r"(?:<command-name>|^)/(sdlc:[\w-]+)(?:</command-name>)?\s*(.*)", re.S)
AUTOMATED = ("Fleet:", "Fleet orchestrator:")  # wake prompts written by fleet.py, not by a human


def from_prompt(base: dict, prompt: str) -> dict | None:
    """A typed /sdlc:<verb> counts as a skill use by the human; wake prompts are not intents; everything else is one."""
    typed = TYPED_SKILL.search(prompt)
    if typed:
        args = re.sub(r"</?command-[a-z]+>", " ", typed.group(2)).strip()
        return {**base, "kind": "skill", "by": "human", "skill": typed.group(1), "args": args[:ARGS_MAX], "ok": True}
    if not prompt or prompt.startswith("<") or prompt.startswith(AUTOMATED):
        return None
    return {**base, "kind": "intent", "by": "human", "text": prompt.replace("\n", " ")[:INTENT_MAX]}


def from_event(event: dict) -> dict | None:
    base = {"cwd": os.path.basename(event.get("cwd", "")), "sid": event.get("session_id")}
    tool, tool_input = event.get("tool_name"), event.get("tool_input", {})
    if event.get("hook_event_name") == "UserPromptSubmit":
        return from_prompt(base, event.get("prompt", "").strip())
    if tool == "Skill":
        return {**base, "kind": "skill", "by": "model", "skill": tool_input.get("skill"), "args": str(tool_input.get("args", ""))[:ARGS_MAX], "ok": outcome(event)}
    if tool == "Bash" and (sig := signature(tool_input.get("command", ""))):
        return {**base, "kind": "cmd", "by": "model", "sig": sig, "ok": outcome(event)}
    return None


def switch_on(rest: list[str]) -> str:
    marker = data_dir() / "telemetry.on"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    return f"telemetry on, local only: {data_dir()}"


def switch_off(rest: list[str]) -> str:
    (data_dir() / "telemetry.on").unlink(missing_ok=True)
    return "telemetry off"


def feedback(rest: list[str]) -> str:
    if not rest:
        return "usage: feedback <text> [about]"
    append({"kind": "feedback", "by": "human", "text": rest[0][:TEXT_MAX], "about": rest[1] if len(rest) > 1 else None}, log="feedback")
    return "feedback recorded"


def status(rest: list[str]) -> str:
    return f"telemetry {'on' if enabled() else 'off'}; log dir {data_dir()}"


COMMANDS = {"on": switch_on, "off": switch_off, "feedback": feedback}


def cli(argv: list[str]) -> int:
    print(COMMANDS.get(argv[0], status)(argv[1:]))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(cli(sys.argv[1:]))
    event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    if record := from_event(event):
        append(record)
