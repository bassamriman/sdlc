#!/usr/bin/env python3
"""End-to-end self-test of the plugin: an autopilot epic on a fixture repo, run unattended, then verified.
CLI: setup [plugin_dir] | wait [minutes] | verify. The fixture lives in the plugin's data dir (SDLC_DATA_DIR or
~/.local/share/sdlc) under e2e/, at a fixed path so the clone is trusted once; SDLC_E2E_ROOT overrides it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import fleet
import record

AGENT, BRANCH, BASE = "sample", "feat/multiply", "main"
ROOT = Path(os.environ.get("SDLC_E2E_ROOT") or record.data_dir() / "e2e")
FILES = {
    "calc.py": "def add(a: int, b: int) -> int:\n    return a + b\n",
    "tests/__init__.py": "",
    "tests/test_calc.py": "import unittest\nfrom calc import add\n\n\nclass CalcTests(unittest.TestCase):\n    def test_add(self) -> None:\n        self.assertEqual(add(2, 3), 5)\n",
    "Makefile": "test:\n\tpython3 -m unittest discover -s tests -t .\n",
    "README.md": "# sample\n\nFixture for the sdlc end-to-end test. `make test` runs the suite.\n",
}
BRIEF = ("Fixture repo. Run the full sdlc loop unattended on one feature: add `multiply(a, b)` to calc.py with a test. "
         "/sdlc:init, /sdlc:plan (one slice), /sdlc:red, /sdlc:step, /sdlc:why, /sdlc:check, commit, git push origin "
         f"{BRANCH}, /sdlc:wrap, then /sdlc:save with **Status**: done. Autopilot is on: do not wait for confirmations.")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def write_fixture(work: Path) -> None:
    work.mkdir()
    for name, text in FILES.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text)
    git(work, "init", "-q", "-b", BASE)
    git(work, "-c", "user.email=e2e@sdlc", "-c", "user.name=sdlc e2e", "add", ".")
    git(work, "-c", "user.email=e2e@sdlc", "-c", "user.name=sdlc e2e", "commit", "-qm", "fixture")


def seed_origin(root: Path) -> Path:
    """A bare origin holding the fixture on main; recreated on every setup so each run starts clean."""
    bare, work = root / "origin" / "sample.git", root / "seed"
    for p in (bare, work):
        shutil.rmtree(p, ignore_errors=True)
    bare.mkdir(parents=True)
    git(bare, "init", "-q", "--bare", "-b", BASE)
    write_fixture(work)
    git(work, "push", "-q", str(bare), BASE)
    shutil.rmtree(work)
    return bare


def reset_clone(root: Path, bare: Path) -> None:
    """Keep the clone path stable (trust is per path); point it at the fresh origin and the base."""
    repo = root / AGENT / "sample"
    if repo.exists():
        git(repo, "remote", "set-url", "origin", str(bare))
        git(repo, "fetch", "-q", "origin")
        git(repo, "checkout", "-q", "-B", BRANCH, f"origin/{BASE}")
        shutil.rmtree(repo / ".claude" / "worktrees", ignore_errors=True)  # nested worktrees would hide .sdlc from fleet status
        git(repo, "worktree", "prune")
        git(repo, "clean", "-qffdx", "-e", ".claude/settings.local.json")


def setup(root: Path, plugin_dir: str | None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    bare = seed_origin(root)
    extra_env = json.loads(os.environ.get("SDLC_E2E_ENV", "{}"))  # e.g. {"GIT_CONSENT_GROUPS": "none"} for a personal consent hook
    definition = {"name": "sdlc-e2e", "base": BASE, "autopilot": True, "env": extra_env, **({"plugin_dir": plugin_dir} if plugin_dir else {}),
                  "agents": [{"name": AGENT, "repo": str(bare), "branch": BRANCH, "brief": BRIEF}]}
    (root / "fleet.json").write_text(json.dumps(definition, indent=2) + "\n")
    reset_clone(root, bare)
    return fleet.init(root / "fleet.json")


def wait(root: Path, minutes: float) -> str:
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        status = fleet.read_status(root, fleet.load_fleet(root)["agents"][0])["status"]
        if status == "done":
            return status
        time.sleep(10)
    return "timeout"


def verify(root: Path) -> dict:
    repo, bare = root / AGENT / "sample", root / "origin" / "sample.git"
    checks = {
        "status_done": fleet.read_status(root, fleet.load_fleet(root)["agents"][0])["status"] == "done",
        "pushed": BRANCH in git(bare, "branch", "--list", BRANCH),
        "ahead_of_base": bool(git(bare, "rev-list", f"{BASE}..{BRANCH}").strip()) if BRANCH in git(bare, "branch", "--list", BRANCH) else False,
        "tests_green": subprocess.run(["make", "test"], cwd=repo, capture_output=True).returncode == 0,
        "multiply_tested": "multiply" in (repo / "tests" / "test_calc.py").read_text(),
        "checked_hash_recorded": "checked_hash" in json.loads((repo / ".sdlc" / "state.json").read_text()) if (repo / ".sdlc" / "state.json").exists() else False,
    }
    return {"ok": all(checks.values()), "checks": checks}


def main(argv: list[str]) -> int:
    cmd, arg = argv[0], argv[1] if len(argv) > 1 else None
    if cmd == "setup":
        print(json.dumps(setup(ROOT, arg), indent=2))
        return 0
    if cmd == "wait":
        status = wait(ROOT, float(arg or 20))
        print(status)
        return 0 if status == "done" else 1
    result = verify(ROOT)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
