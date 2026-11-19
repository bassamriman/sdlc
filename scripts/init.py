#!/usr/bin/env python3
"""Mechanical part of /sdlc:init: write .sdlc/stack.json from the best pack, exclude .sdlc from git, record the base, start a timebox when minutes are given."""
from __future__ import annotations

import json
import shutil
import sys

import detect
import state as st


def write_stack(root, pack: dict) -> dict:
    target = root / ".sdlc" / "stack.json"
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        return json.loads(target.read_text())
    target.write_text(json.dumps(pack, indent=2) + "\n")
    return pack


def main(argv: list[str]) -> int:
    root = st.root()
    stack = write_stack(root, detect.best_pack(root))
    st.exclude_from_git(root)
    st.main(["state.py", "base"])
    minutes = next((a for a in argv if a.isdigit()), None)
    if minutes:
        st.main(["state.py", "start", minutes])
    state = st.load()
    print(json.dumps({"pack": stack.get("pack"), "check": stack.get("check"), "commands": stack.get("commands"),
                      "base": state.get("base_ref"), "timebox_min": state.get("budget_min"),
                      "tools_missing": [t for t in ("gh", "uv", "pnpm", "make") if not shutil.which(t)]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
