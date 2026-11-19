#!/usr/bin/env python3
"""SessionStart: name the verbs and report repo state (pack, base, plan, timebox)."""
from __future__ import annotations

import json
import os
import re
import sys

import state as st

event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
root = st.root(event.get("cwd"))
state = st.load(event.get("cwd"))
print("sdlc verbs: init orient clarify plan red step why check debug review standards arch diagram wrap | pr rebase save load | "
      "ide telemetry feedback reflect | fleet orchestrate par")
print("Flow: orient > clarify > plan > (red > step > why > check > commit)* > standards/arch > wrap. Tiny change: skip plan.")
if workspace := os.environ.get("SDLC_AGENT_WORKSPACE"):
    print(f"Fleet agent workspace: {workspace} (edits outside it are denied; gates: {os.environ.get('SDLC_GATES', 'default')}).")
    if os.environ.get("SDLC_FLEET_ROOT"):
        import bus
        fleet_root, me = bus.identity()
        unread = bus.unread_count(fleet_root, me)
        print(f"Fleet bus: you are {me}; {unread} unread message(s). Read: python3 \"$PLUGIN/scripts/bus.py\" inbox; send: bus.py send <agent|all|orchestrator> <text>."
              .replace("$PLUGIN", os.path.dirname(os.path.abspath(__file__)) + "/.."))
if not (root / ".sdlc" / "stack.json").exists():
    print("Stack pack: none, run /sdlc:init")
else:
    plan = root / ".sdlc" / "plan.md"
    slices = len(re.findall(r"^\s*-?\s*Slice\s+\d+", plan.read_text(), re.M)) if plan.exists() else 0
    print(f"Stack pack: loaded. Base: {state.get('base_ref') or 'unset'}. Plan: {f'{slices} slices in .sdlc/plan.md' if slices else 'none'}.")
    context = root / ".sdlc" / "context.md"
    if context.exists():
        digest = re.findall(r"^\*\*(Status|Branch|Next)\*\*:?\s*(.+)$", context.read_text(), re.M)
        print("Saved context: " + " | ".join(f"{k}: {v.strip()[:120]}" for k, v in digest) + ". Run /sdlc:load to resume.")
        lines = context.read_text().count("\n")
        if lines > 40:
            print(f"Saved context is {lines} lines (cap 40): /sdlc:save must prune it, it is reloaded in full every session.")
    line = st.tick(state)
    if line:
        print(line)
