#!/usr/bin/env python3
"""Fleet reporting, mechanical not remembered. PostToolUse(Edit|Write): when an agent rewrites .sdlc/context.md, post its status
line to the orchestrator. Library: notify(text) posts to the orchestrator's inbox and wakes it when idle. Inert outside a fleet."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import bus
import fleet

STATUS = re.compile(r"\*\*(Status|PR)\*\*:?[ \t]*([^*\n]+)")


def wake_orchestrator(root: Path) -> None:
    """Detached, so a hook never waits on claude; only when the orchestrator is idle (a busy one sees the nudge next turn)."""
    if fleet.session_state(root, bus.ORCHESTRATOR) not in ("idle", "stopped"):
        return
    text = "Fleet: an agent reported; run fleet.py orchestrate --run, read your inbox, update context.md."
    subprocess.Popen([sys.executable, str(Path(__file__).with_name("fleet.py")), "wake", bus.ORCHESTRATOR, text, "--run"],
                     cwd=root, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify(text: str) -> bool:
    if not os.environ.get("SDLC_FLEET_ROOT") or not os.environ.get("SDLC_AGENT_WORKSPACE"):
        return False
    root, me = bus.identity()
    if me == bus.ORCHESTRATOR:
        return False
    bus.send((root, me), bus.ORCHESTRATOR, text)
    wake_orchestrator(root)
    return True


def main() -> int:
    event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    path = event.get("tool_input", {}).get("file_path", "")
    if not path.endswith("/.sdlc/context.md") or not os.path.isfile(path):
        return 0
    fields = dict(STATUS.findall(open(path, encoding="utf-8", errors="replace").read()))
    if fields.get("Status") and notify(f"status {fields['Status'].strip()}; pr {fields.get('PR', 'none').strip()}"):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "sdlc fleet: status reported to the orchestrator."}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
