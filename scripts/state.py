#!/usr/bin/env python3
"""Per-repo session state in .sdlc/state.json: base ref, timebox, phase, last green tree. Python 3.9+."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

PHASES = (("orient", 0.10), ("plan", 0.20), ("build", 0.76), ("wrap", 1.0))
THIN = 0.57
EXCLUDE = (".", ":(exclude).sdlc")
BASE_CANDIDATES = ("origin/HEAD", "origin/main", "origin/master", "main", "master")
BIG_FILE = 2_000_000
TIMEBOX_KEYS = ("started", "budget_min", "phase")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout


def root(cwd: str | None = None) -> Path:
    base = Path(cwd or ".")
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=base, capture_output=True, text=True)
    return Path(out.stdout.strip()) if out.returncode == 0 else base.resolve()


def path(cwd: str | None = None) -> Path:
    return root(cwd) / ".sdlc" / "state.json"


def load(cwd: str | None = None) -> dict:
    try:
        return json.loads(path(cwd).read_text())
    except (OSError, ValueError):
        return {}


def exclude_from_git(r: Path) -> None:
    exclude = r / ".git" / "info" / "exclude"
    if not exclude.parent.exists():
        return
    text = exclude.read_text() if exclude.exists() else ""
    if ".sdlc/" not in text:
        exclude.write_text(text.rstrip("\n") + "\n.sdlc/\n")


def save(state: dict, cwd: str | None = None) -> None:
    p = path(cwd)
    p.parent.mkdir(exist_ok=True)
    exclude_from_git(p.parent.parent)
    p.write_text(json.dumps(state, indent=2))


def changed_paths(r: Path) -> list[str]:
    """Paths with uncommitted changes, NUL-separated so non-ASCII, spaces and quotes survive; a rename yields its new name."""
    entries, names, i = git(r, "-c", "core.quotepath=off", "status", "--porcelain=v1", "-z", "-uall", "--", *EXCLUDE).split("\0"), [], 0
    while i < len(entries):
        entry = entries[i]
        if entry:
            names.append(entry[3:])
            if entry[0] in "RC":
                i += 1
        i += 1
    return sorted(names)


def file_digest(f: Path) -> bytes:
    """Content for ordinary files; size plus mtime for big ones, so an in-place edit still changes the hash."""
    try:
        stat = f.stat()
        return f.read_bytes() if stat.st_size < BIG_FILE else f"{stat.st_size}:{stat.st_mtime_ns}".encode()
    except OSError:
        return b"gone"


def tree_hash(cwd: str | None = None) -> str:
    r = root(cwd)
    digest = hashlib.sha1()
    for name in changed_paths(r):
        digest.update(name.encode())
        digest.update(file_digest(r / name))
    return digest.hexdigest()


def base_ref(r: Path) -> tuple[str, str] | None:
    for ref in BASE_CANDIDATES:
        out = subprocess.run(["git", "merge-base", "HEAD", ref], cwd=r, capture_output=True, text=True)
        if out.returncode == 0:
            return git(r, "rev-parse", "--abbrev-ref", ref).strip() or ref, out.stdout.strip()
    return None


def tick(state: dict) -> str | None:
    started, budget = state.get("started"), state.get("budget_min")
    if not started or not budget:
        return None
    elapsed = (time.time() - started) / 60
    if elapsed > 2 * budget:
        return None
    phase = state.get("phase", "orient")
    limit = next((budget * frac for name, frac in PHASES if name == phase), budget)
    flag = " BEHIND: cut scope, ship the thin version" if elapsed > limit else ""
    lines = [f"[timebox] {elapsed:.0f}/{budget}m, phase {phase} (due {limit:.0f}m){flag}"]
    if phase == "build" and THIN * budget <= elapsed <= limit:
        lines.append(f"[timebox] thin working version was due at {THIN * budget:.0f}m: ship it before polishing")
    return "\n".join(lines)


def record_base(state: dict) -> dict:
    found = base_ref(root())
    return {**state, "base_ref": found[0], "base_sha": found[1]} if found else state


SKILL_PHASE = {"sdlc:orient": "orient", "sdlc:clarify": "plan", "sdlc:plan": "plan", "sdlc:red": "build", "sdlc:step": "build", "sdlc:wrap": "wrap"}


def phase_hook() -> int:
    """PostToolUse on Skill: the skill that ran sets the timebox phase, so no skill has to call `state.py phase`."""
    event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    phase = SKILL_PHASE.get(str(event.get("tool_input", {}).get("skill", "")))
    cwd = event.get("cwd")
    if phase and (root(cwd) / ".sdlc").exists():
        state = load(cwd)
        if state.get("phase") != phase:
            save({**state, "phase": phase}, cwd)
    return 0


TRANSITIONS = {
    "start": lambda s, a: {**s, "started": time.time(), "budget_min": int(a[0]), "phase": "orient"},
    "stop": lambda s, a: {k: v for k, v in s.items() if k not in TIMEBOX_KEYS},
    "phase": lambda s, a: {**s, "phase": a[0]},
    "base": lambda s, a: record_base(s),
    "set": lambda s, a: {**s, a[0]: a[1]},
    "unset": lambda s, a: {k: v for k, v in s.items() if k not in a},
    "mark-checked": lambda s, a: {**s, "checked_hash": tree_hash()},
}


def main(argv: list[str]) -> int:
    cmd, args = (argv[1] if len(argv) > 1 else "show"), argv[2:]
    if cmd == "hook":
        return phase_hook()
    state = load()
    if cmd in TRANSITIONS:
        save(TRANSITIONS[cmd](state, args))
    elif cmd == "tick":
        line = tick(state)
        if line:
            print(line)
    else:
        print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
