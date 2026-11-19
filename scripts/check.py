#!/usr/bin/env python3
"""Run the stack's check sequence in order, stop at the first failure, record a green tree."""
from __future__ import annotations

import json
import subprocess
import sys

import state as st


def run(command: str, cwd) -> tuple[bool, str]:
    out = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)
    tail = "\n".join((out.stdout + out.stderr).strip().splitlines()[-12:])
    return out.returncode == 0, tail


def load_stack(root) -> dict | str:
    """The parsed stack, or the line to print when it cannot be used."""
    target = root / ".sdlc" / "stack.json"
    if not target.exists():
        return "no .sdlc/stack.json: run /sdlc:init"
    try:
        return json.loads(target.read_text())
    except ValueError as exc:
        return f"malformed .sdlc/stack.json ({exc}): fix it or delete it and run /sdlc:init"


def run_one(name: str, command: str, root) -> bool:
    ok, tail = run(command, root)
    print(f"{'PASS' if ok else 'FAIL'} {name}: {command}")
    if not ok:
        print(tail)
    return ok


def run_checks(stack: dict, root) -> bool:
    """True only when at least one command ran and every one passed; stops at the first failure."""
    commands, ran = stack.get("commands", {}), 0
    for name in stack.get("check", []):
        if not commands.get(name):
            print(f"SKIP {name}: no command in stack.json")
            continue
        ran += 1
        if not run_one(name, commands[name], root):
            return False
    if ran == 0:
        print("RED: nothing ran; fill commands in .sdlc/stack.json")
    return ran > 0


def main() -> int:
    root = st.root()
    stack = load_stack(root)
    if isinstance(stack, str):
        print(stack)
        return 2
    if not run_checks(stack, root):
        return 1
    st.main(["state.py", "mark-checked"])
    print("GREEN: tree recorded, commit is unblocked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
