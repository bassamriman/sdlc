#!/usr/bin/env python3
"""Open the project, or file[:line], in the IDE that matches the stack. `--print` shows the command only."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import detect
import state as st

IDE_BY_LANGUAGE = {"python": "pycharm", "java": "idea", "kotlin": "idea", "scala": "idea",
                   "go": "goland", "rust": "rustrover", "typescript": "webstorm"}
LAUNCHERS = {"pycharm": ("pycharm", "charm"), "idea": ("idea",), "goland": ("goland",), "rustrover": ("rustrover",),
             "webstorm": ("webstorm",), "code": ("code",), "cursor": ("cursor",)}
APPS = {"pycharm": ("PyCharm", "PyCharm CE"), "idea": ("IntelliJ IDEA", "IntelliJ IDEA CE"), "goland": ("GoLand",),
        "rustrover": ("RustRover",), "webstorm": ("WebStorm",), "code": ("Visual Studio Code",), "cursor": ("Cursor",)}
TOOLBOX = Path.home() / "Library/Application Support/JetBrains/Toolbox/scripts"


@dataclass(frozen=True)
class Target:
    root: Path
    file: str | None
    line: int | None
    print_only: bool


def parse(argv: list[str]) -> Target:
    args = [a for a in argv if a != "--print"]
    file, line = (args[0].rsplit(":", 1) + [None])[:2] if args and ":" in args[0] else ((args[0] if args else None), None)
    return Target(st.root(), file, int(line) if line and line.isdigit() else None, "--print" in argv)


def choose_ide(root: Path) -> str:
    try:
        stack = json.loads((root / ".sdlc" / "stack.json").read_text())
    except (OSError, ValueError):
        stack = {}
    if stack.get("ide"):
        return stack["ide"]
    languages = stack.get("languages") or detect.languages(root)
    return next((IDE_BY_LANGUAGE[lang] for lang in languages if lang in IDE_BY_LANGUAGE), "code")


def launcher(ide: str) -> list[str] | None:
    for name in LAUNCHERS.get(ide, ()):
        found = shutil.which(name) or shutil.which(name, path=str(TOOLBOX))
        if found:
            return [found]
    for app in APPS.get(ide, ()):
        if any((base / f"{app}.app").exists() for base in (Path("/Applications"), Path.home() / "Applications")):
            return ["open", "-a", app]
    return None


def command(ide: str, base: list[str], target: Target) -> list[str]:
    path = str(target.root / target.file) if target.file else str(target.root)
    if base[0] == "open":
        return [*base, path]
    if target.line and ide in ("code", "cursor"):
        return [*base, "-g", f"{path}:{target.line}"]
    if target.line:
        return [*base, "--line", str(target.line), path]
    return [*base, path]


def main(argv: list[str]) -> int:
    target = parse(argv)
    ide = choose_ide(target.root)
    base = launcher(ide)
    if not base:
        print(f"{ide}: no launcher found. Install its shell script (JetBrains Toolbox > Settings > Shell scripts) "
              f'or set "ide" in .sdlc/stack.json to one of {sorted(LAUNCHERS)}.')
        return 1
    cmd = command(ide, base, target)
    if target.print_only:
        print(" ".join(cmd))
        return 0
    subprocess.Popen(cmd, cwd=target.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"opened {target.file or target.root.name} in {ide}" + (f" at line {target.line}" if target.line else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
