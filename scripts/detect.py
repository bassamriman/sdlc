#!/usr/bin/env python3
"""Match the repo against the marker groups declared in stacks/*.json; print the best pack and repo facts as JSON."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import state as st

STACKS = Path(__file__).resolve().parent.parent / "stacks"


def packs() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(STACKS.glob("*.json"))]


def repo_paths(root: Path) -> list[str]:
    tracked = st.git(root, "ls-files").splitlines()
    untracked = st.git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    return [p for p in tracked + untracked if "node_modules" not in p]


def marker_names(paths: list[str]) -> tuple[set[str], set[str]]:
    """Names seen anywhere (basenames plus '*.ext') and names seen at the repo root."""
    extensions = {"*" + os.path.splitext(p)[1] for p in paths if os.path.splitext(p)[1]}
    return {os.path.basename(p) for p in paths} | extensions, {p for p in paths if "/" not in p}


def score(pack: dict, everywhere: set[str], at_root: set[str]) -> tuple[int, int] | None:
    """(groups matched, groups matched at the root); None unless every group matches."""
    groups = pack.get("markers", [])
    if not all(any(n in everywhere for n in group) for group in groups):
        return None
    return len(groups), sum(any(n in at_root for n in group) for group in groups)


def best_pack(root: Path) -> dict:
    everywhere, at_root = marker_names(repo_paths(root))
    scored = [(s, p) for p in packs() if (s := score(p, everywhere, at_root)) is not None]
    return max(scored, key=lambda sp: sp[0])[1] if scored else {"pack": "generic", "languages": []}


def languages(root: Path) -> list[str]:
    return best_pack(root).get("languages", [])


def main() -> None:
    root = st.root()
    pack = best_pack(root)
    makefile = root / "Makefile"
    targets = re.findall(r"^([A-Za-z][\w-]*):", makefile.read_text(), re.M) if makefile.exists() else []
    claude_md = [str(p.relative_to(root)) for p in root.glob("**/CLAUDE.md") if "node_modules" not in str(p)]
    print(json.dumps({"root": str(root), "pack": pack["pack"], "languages": pack.get("languages", []),
                      "make_targets": targets, "claude_md": claude_md, "base": st.base_ref(root)}, indent=2))


if __name__ == "__main__":
    sys.exit(main())
