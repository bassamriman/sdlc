#!/usr/bin/env python3
"""End-to-end test of orchestration: three agents on one fixture repo with a start edge and a merge edge, autopilot gates and the
diagram gate, driven by the orchestrator session. CLI: setup [plugin_dir] | run [plugin_dir] [minutes] | merge <agent> | verify.
`run` = setup, start the orchestrator session, then play the human: step the fleet, merge each branch as it reports pr-open, until
epic_done. Root: SDLC_E2E_FLEET_ROOT or <data dir>/e2e-fleet, fixed so clones are trusted once."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import bus
import e2e
import fleet
import record

ROOT = Path(os.environ.get("SDLC_E2E_FLEET_ROOT") or record.data_dir() / "e2e-fleet")
BASE = "main"
FILES = {
    "shop/__init__.py": "",
    "shop/contracts.py": "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass Item:\n    name: str\n    price_cents: int\n",
    "shop/api.py": "from shop.contracts import Item\n\n\ndef items() -> list[Item]:\n    return [Item('pen', 150), Item('pad', 400)]\n",
    "shop/web.py": "from shop.api import items\n\n\ndef page() -> str:\n    return ', '.join(i.name for i in items())\n",
    "tests/__init__.py": "",
    "tests/test_shop.py": "import unittest\nfrom shop.web import page\n\n\nclass ShopTests(unittest.TestCase):\n    def test_page(self) -> None:\n        self.assertEqual(page(), 'pen, pad')\n",
    "Makefile": "test:\n\tpython3 -m unittest discover -s tests -t .\n",
    "README.md": "# shop\n\nFixture for the sdlc orchestration test.\n",
}
FORMAT_RULE = "# Display format\nTotals render as `Order total: <cents> cents`, for example `Order total: 550 cents`. Never a dollar sign.\n"
COMMON = (" Full sdlc loop, autopilot: /sdlc:init, /sdlc:plan one slice, /sdlc:red, /sdlc:step, /sdlc:why, run archdiff.py and git add docs/arch/, "
          "/sdlc:check, commit, push your branch, /sdlc:wrap, /sdlc:save with **Status**: pr-open (there is no gh here: pushed means pr-open). "
          "When a fleet message says the base moved: /sdlc:load, /sdlc:rebase, /sdlc:check, re-read this brief, /sdlc:save.")
AGENTS = [
    {"name": "contracts", "branch": "feat/order-total", "brief": "In shop/contracts.py add a frozen dataclass OrderTotal(cents: int, currency: str = 'USD') with a classmethod of_items(items) summing price_cents. Test it." + COMMON},
    {"name": "api", "branch": "feat/total-endpoint", "depends": [{"on": "contracts", "phase": "start"}],
     "brief": "In shop/api.py add total() -> OrderTotal using OrderTotal.of_items from shop/contracts.py (the contracts agent publishes it; if it is not on your base yet, rebase onto origin/main first). Test it." + COMMON},
    {"name": "web", "branch": "feat/total-line", "depends": [{"on": "api", "phase": "merge"}],
     "brief": "In shop/web.py add total_line() -> str that renders the total in the format given in the epic's resources/ (read it); use api.total() when it exists, else sum items() yourself; keep page() unchanged. Test it." + COMMON},
]


def fresh_origin() -> Path:
    """A bare origin holding the fixture on main; orchestrator run state is wiped with it."""
    bare, work = ROOT / "origin" / "shop.git", ROOT / "seed"
    for p in (bare, work, ROOT / "orchestrator" / "launched.json", ROOT / "orchestrator" / "base.sha", ROOT / "orchestrator" / "sessions.json"):
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    bare.mkdir(parents=True)
    e2e.git(bare, "init", "-q", "--bare", "-b", BASE)
    e2e.FILES, saved = FILES, e2e.FILES
    e2e.write_fixture(work)
    e2e.FILES = saved
    e2e.git(work, "push", "-q", str(bare), BASE)
    shutil.rmtree(work)
    return bare


def reset_clone(repo: Path, bare: Path, branch: str) -> None:
    """Keep the clone path (trust is per path) but start it from the fresh origin on its branch, with no saved state."""
    e2e.git(repo, "remote", "set-url", "origin", str(bare))
    e2e.git(repo, "fetch", "-q", "origin")
    e2e.git(repo, "checkout", "-q", "-B", branch, f"origin/{BASE}")
    e2e.git(repo, "clean", "-qffdx", "-e", ".claude/settings.local.json")
    shutil.rmtree(repo / ".sdlc", ignore_errors=True)


def setup(plugin_dir: str | None) -> dict:
    ROOT.mkdir(parents=True, exist_ok=True)
    bare = fresh_origin()
    extra_env = json.loads(os.environ.get("SDLC_E2E_ENV", "{}"))
    definition = {"name": "sdlc-e2e-fleet", "base": BASE, "autopilot": True, "effort": "medium", "gates": {"diagram": "require"}, "env": extra_env,
                  **({"plugin_dir": plugin_dir} if plugin_dir else {}), "agents": [{**a, "repo": str(bare)} for a in AGENTS]}
    (ROOT / "fleet.json").write_text(json.dumps(definition, indent=2) + "\n")
    (ROOT / "resources").mkdir(exist_ok=True)
    (ROOT / "resources" / "format.md").write_text(FORMAT_RULE)  # only an agent that reads resources/ gets this right
    for agent in definition["agents"]:
        if fleet.repo_dir(ROOT, agent).exists():
            reset_clone(fleet.repo_dir(ROOT, agent), bare, agent["branch"])
    for stale in list(ROOT.glob("*/outbox.jsonl")) + list(ROOT.glob("*/inbox.cursor")):
        stale.unlink()
    return fleet.init(ROOT / "fleet.json")


def merge(agent: str) -> str:
    """Simulate the human merging that agent's PR: fast-forward only. A branch not rebased onto the base is refused, like a PR with conflicts."""
    bare = ROOT / "origin" / "shop.git"
    branch = next(a["branch"] for a in AGENTS if a["name"] == agent)
    tip, base = e2e.git(bare, "rev-parse", branch).strip(), e2e.git(bare, "rev-parse", BASE).strip()
    if subprocess.run(["git", "merge-base", "--is-ancestor", base, tip], cwd=bare).returncode != 0:
        raise SystemExit(f"refused: {branch} ({tip[:8]}) does not contain {BASE} ({base[:8]}); the agent must rebase first")
    e2e.git(bare, "update-ref", f"refs/heads/{BASE}", tip, base)
    return tip


def branch_exists(agent: str) -> bool:
    bare = ROOT / "origin" / "shop.git"
    branch = next(a["branch"] for a in AGENTS if a["name"] == agent)
    return branch in e2e.git(bare, "branch", "--list", branch)


def mergeable(agent: str) -> bool:
    """The base is contained in the branch: a fast-forward merge is possible."""
    bare = ROOT / "origin" / "shop.git"
    branch = next(a["branch"] for a in AGENTS if a["name"] == agent)
    return branch_exists(agent) and subprocess.run(["git", "merge-base", "--is-ancestor", BASE, branch], cwd=bare).returncode == 0


def landed(agent: str) -> bool:
    """The branch is contained in the base: its work has been merged."""
    bare = ROOT / "origin" / "shop.git"
    branch = next(a["branch"] for a in AGENTS if a["name"] == agent)
    return branch_exists(agent) and subprocess.run(["git", "merge-base", "--is-ancestor", branch, BASE], cwd=bare).returncode == 0


def merge_ready(merged: list[str]) -> None:
    """The human's part: merge every branch that reports pr-open and fast-forwards cleanly."""
    for agent in AGENTS:
        status = fleet.read_status(ROOT, {**agent, "repo": str(ROOT / "origin" / "shop.git")})["status"]
        if status == "pr-open" and agent["name"] not in merged and mergeable(agent["name"]):
            merge(agent["name"])
            merged.append(agent["name"])


def run(plugin_dir: str | None, minutes: float) -> dict:
    """Setup, start the orchestrator session, then act as the human merger until epic_done or the deadline."""
    setup(plugin_dir)
    fleet.up(ROOT, run=True)
    deadline, merged, woken, steps = time.time() + minutes * 60, [], 0, 0
    while time.time() < deadline:
        step = fleet.orchestrate(ROOT, run=True)
        steps, woken = steps + 1, woken + len(step["woken"])
        merge_ready(merged)
        if step["epic_done"]:
            break
        time.sleep(30)
    return {"epic_done": step["epic_done"], "steps": steps, "merged": merged, "woken": woken}


def checks(agents: list[dict], messages: list[dict], listed: list[dict]) -> dict:
    context = ROOT / "orchestrator" / "context.md"
    return {
        "all_done": all(fleet.read_status(ROOT, a)["status"] == "done" for a in agents),
        "all_landed": all(landed(a["name"]) for a in agents),
        "diagram_in_every_branch": all((fleet.repo_dir(ROOT, a) / "docs" / "arch").exists() for a in agents),
        "resources_were_read": "Order total:" in ((fleet.repo_dir(ROOT, agents[2]) / "shop" / "web.py").read_text() if (fleet.repo_dir(ROOT, agents[2]) / "shop" / "web.py").exists() else ""),
        "agents_reported_to_orchestrator": {a["name"] for a in agents} <= {r["from"] for r in messages if r["to"] == "orchestrator"},
        "base_moved_broadcast": any(r["to"] == "all" and "moved to" in r["text"] for r in messages),
        "orchestrator_answered_an_agent": any(r["from"] == "orchestrator" and r["to"] in {a["name"] for a in agents} for r in messages),
        "orchestrator_context_saved": context.exists() and "**Status**" in context.read_text(),
        "no_stray_sessions": all(r.get("name", "").startswith("sdlc/sdlc-e2e-fleet/") for r in listed),
    }


def verify() -> dict:
    """Mechanical checks over everything the orchestration path must have done; ok only when all pass."""
    agents = [{**a, "repo": str(ROOT / "origin" / "shop.git")} for a in AGENTS]
    messages = bus.all_messages(ROOT)
    listed = [r for r in fleet.listed_sessions() if r.get("cwd", "").startswith(str(ROOT))]
    result = checks(agents, messages, listed)
    return {"ok": all(result.values()), "checks": result, "messages": len(messages), "sessions_listed": len(listed)}


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "verify"
    if cmd == "setup":
        print(json.dumps(setup(argv[1] if len(argv) > 1 else None), indent=2))
    elif cmd == "run":
        plugin_dir = next((a for a in argv[1:] if not a.replace(".", "").isdigit()), None)
        minutes = next((float(a) for a in argv[1:] if a.replace(".", "").isdigit()), 30)
        result = run(plugin_dir, minutes)
        print(json.dumps({**result, **verify()}, indent=2))
        return 0 if result["epic_done"] and verify()["ok"] else 1
    elif cmd == "merge":
        print(json.dumps({"merged": argv[1], "base_now": merge(argv[1])[:12]}))
    else:
        print(json.dumps(verify(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
