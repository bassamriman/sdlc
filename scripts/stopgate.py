#!/usr/bin/env python3
"""Stop hook for fleet agents: keep going while the plan has work left. A turn may end when the saved status is not
in-progress (blocked, pr-open, done), or when no commit landed since the last nudge (stuck, so never loop). Inert
outside a fleet and for the orchestrator."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

NUDGE = ("sdlc fleet: your plan still has work and **Status** is in-progress. Continue with the next slice now "
         "(/sdlc:red); when every slice is committed run /sdlc:wrap then /sdlc:pr open; if you cannot continue, "
         "save **Status**: blocked with the reason and stop.")


def clone(workspace: Path) -> Path:
    """The agent's clone: the workspace when it is a repository, else its one child that is."""
    if (workspace / ".git").exists():
        return workspace
    return next((p for p in sorted(workspace.iterdir()) if (p / ".git").exists()), workspace)


def saved_status(repo: Path) -> str:
    context = repo / ".sdlc" / "context.md"
    lines = context.read_text().splitlines() if context.exists() else []
    line = next((l for l in lines if l.startswith("**Status**")), "")
    return line.split(":", 1)[-1].strip().lower() or "in-progress"


def head(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def should_continue(repo: Path) -> bool:
    """In progress, with a plan, and a commit landed since the last nudge (or no nudge yet)."""
    if not (repo / ".sdlc" / "plan.md").exists() or not saved_status(repo).startswith("in-progress"):
        return False
    marker = repo / ".sdlc" / "nudged-at"
    now = head(repo)
    if marker.exists() and marker.read_text().strip() == now:
        return False  # nudged before and nothing was committed since: stuck, let the turn end
    marker.write_text(now)
    return True


def main() -> int:
    if not sys.stdin.isatty():
        json.load(sys.stdin)
    workspace = os.environ.get("SDLC_AGENT_WORKSPACE")
    if not workspace or os.environ.get("SDLC_AGENT_NAME") == "orchestrator":
        return 0
    if should_continue(clone(Path(workspace))):
        print(json.dumps({"decision": "block", "reason": NUDGE}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # a broken stop hook must never trap a session
        sys.exit(0)
