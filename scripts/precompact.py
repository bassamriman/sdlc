#!/usr/bin/env python3
"""PreCompact: stdout becomes the compaction instructions. Keep what resuming a slice needs."""
from __future__ import annotations

import json
import sys

import state as st

event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
root = st.root(event.get("cwd"))
if (root / ".sdlc" / "stack.json").exists():
    print("Preserve verbatim: the active slice and its failing test name, the plan's remaining slices, decisions made and "
          "their reasons, open questions, the base ref, and the single next command. Drop tool output and superseded diffs. "
          "If .sdlc/context.md is stale, say so first so the user can run /sdlc:save.")
