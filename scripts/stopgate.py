#!/usr/bin/env python3
"""Stop hook for fleet agents: refuse to end the turn while work changed after the last /sdlc:save. Inert outside a fleet."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def newest_change(repo: Path) -> float:
    """Latest mtime among uncommitted files outside .sdlc/, or the HEAD commit time."""
    names = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=repo, capture_output=True, text=True).stdout.splitlines()
    times = [(repo / n[3:]).stat().st_mtime for n in names if not n[3:].startswith(".sdlc/") and (repo / n[3:]).exists()]
    head = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=repo, capture_output=True, text=True).stdout.strip()
    return max([*times, float(head or 0)])


def clone(workspace: Path) -> Path:
    """The agent's clone: the workspace when it is a repository, else its one child that is."""
    if (workspace / ".git").exists():
        return workspace
    return next((p for p in sorted(workspace.iterdir()) if (p / ".git").exists()), workspace)


def main() -> int:
    event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    workspace = os.environ.get("SDLC_AGENT_WORKSPACE")
    if not workspace or os.environ.get("SDLC_AGENT_NAME") == "orchestrator" or event.get("stop_hook_active"):
        return 0  # a second stop in a row is let through, so the hook can never trap a session
    repo = clone(Path(workspace))
    context = repo / ".sdlc" / "context.md"
    saved = context.stat().st_mtime if context.exists() else 0.0
    if newest_change(repo) > saved:
        print(json.dumps({"decision": "block", "reason": "sdlc fleet: work changed since the last /sdlc:save; run /sdlc:save, then stop"}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # a broken stop gate must never trap a session
        sys.exit(0)
