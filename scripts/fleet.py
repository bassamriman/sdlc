#!/usr/bin/env python3
"""Multi-repo fleet: one workspace and one named Claude session per agent. Waves come from the dependency graph plus
each workspace's saved context; status is computed, never messaged. CLI: init <fleet.json> [--root <dir>] | status | waves |
launch <agent|orchestrator> [--run] | up [--run] | fanout <text> [--run] | wake <agent> [text] [--run] | prune [--done] [--run] | orchestrate [--run] [--wait <seconds>]."""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bus
import gates

STARTED = {"in-progress", "blocked", "pr-open", "done"}
EXISTS = {"pr-open", "done"}
RUNNING = {"in-progress", "blocked", "pr-open"}


def _load(path: Path, default):
    """A cache file that is missing or corrupt reads as empty; the next write repairs it."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _store(path: Path, value) -> None:
    """Write a cache atomically, so a crash mid-write never leaves a half file."""
    path.parent.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2))
    os.replace(tmp, path)


def find_root(start: Path) -> Path | None:
    return next((p for p in (start, *start.parents) if (p / ".sdlc" / "fleet.json").exists()), None)


def load_fleet(root: Path) -> dict:
    return json.loads((root / ".sdlc" / "fleet.json").read_text())


def repo_dir(root: Path, agent: dict) -> Path:
    source = agent.get("repo") or agent.get("path", "")
    return root / agent["name"] / Path(source.rstrip("/")).name.removesuffix(".git")


def read_status(root: Path, agent: dict) -> dict:
    repo = repo_dir(root, agent)
    sdlc = repo / ".sdlc"
    status, pr = "not-started", None
    if (sdlc / "context.md").exists():
        line = next((l for l in (sdlc / "context.md").read_text().splitlines() if l.startswith("**Status**")), "")
        status = line.split(":", 1)[-1].strip() or "in-progress"
    if (sdlc / "state.json").exists():
        pr = json.loads((sdlc / "state.json").read_text()).get("pr_url")
    return {"name": agent["name"], "status": status if repo.exists() else "no-workspace", "pr": pr, "path": str(repo)}


def deps(agent: dict, phase: str) -> list[str]:
    return [d["on"] for d in agent.get("depends", []) if d.get("phase", "start") == phase]


def classify(agent: dict, status: dict) -> tuple[str, object]:
    """The wave bucket an agent falls in and the payload recorded there."""
    name, current = agent["name"], status[agent["name"]]["status"]
    if current == "done":
        return "done", name
    if current in RUNNING:
        waits = [d for d in deps(agent, "merge") if status[d]["status"] != "done"]
        return "running", {"name": name, "status": current, "pr": status[name]["pr"], "cannot_land_until": waits}
    blockers = [d for d in deps(agent, "start") if status[d]["status"] not in EXISTS]
    return ("blocked", (name, blockers)) if blockers else ("ready", name)


def waves(root: Path) -> dict:
    fleet = load_fleet(root)
    status = {a["name"]: read_status(root, a) for a in fleet["agents"]}
    out = {"epic": fleet["name"], "ready": [], "blocked": {}, "running": [], "done": []}
    for agent in fleet["agents"]:
        bucket, payload = classify(agent, status)
        if bucket == "blocked":
            out["blocked"][payload[0]] = payload[1]
        else:
            out[bucket].append(payload)
    return out


def sessions_file(root: Path) -> Path:
    return root / bus.ORCHESTRATOR / "sessions.json"


def listed_sessions() -> list[dict]:
    try:
        out = subprocess.run(["claude", "agents", "--json", "--all"], capture_output=True, text=True)
    except OSError:  # no claude on PATH
        return []
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else []


def session_name(root: Path, name: str) -> str:
    return f"sdlc/{load_fleet(root)['name']}/{name}"


def session_id(root: Path, name: str) -> str | None:
    """The real session id, found by session name (claude --bg assigns ids itself) and cached in orchestrator/sessions.json."""
    path = sessions_file(root)
    ids = _load(path, {})
    rows = [r for r in listed_sessions() if r.get("name") == session_name(root, name) and r.get("sessionId")]
    if not rows:
        return ids.get(name)  # the cache only stands in when claude cannot be listed
    newest = max(rows, key=lambda r: r.get("startedAt", 0))["sessionId"]  # a relaunch supersedes an older session of the same name
    if ids.get(name) != newest:
        ids[name] = newest
        _store(path, ids)
    return newest


def alive(row: dict) -> bool:
    """A listed session may be finished yet still have a live process; resuming it then forks a copy."""
    pid = row.get("pid")
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def session_row(root: Path, name: str) -> dict | None:
    sid = session_id(root, name)
    return next((r for r in listed_sessions() if sid and r.get("sessionId") == sid), None)


def session_state(root: Path, name: str) -> str:
    """busy | idle (finished, process alive) | stopped (no process, or unlisted but resumable by cached id) | absent (never started)."""
    row = session_row(root, name)
    if row is None:
        return "stopped" if session_id(root, name) else "absent"  # agent view may drop a finished session; its conversation still resumes
    if row.get("status") == "busy" or row.get("state") == "working":
        return "busy"
    return "idle" if alive(row) else "stopped"


def stop_and_wait(root: Path, name: str, seconds: float = 20) -> bool:
    """Stop the session's process and wait until it is gone, so a resume continues the same session instead of forking a copy."""
    sid = session_id(root, name)
    subprocess.run(["claude", "stop", sid[:8]], capture_output=True)  # the CLI takes the short id; the full uuid is silently ignored
    deadline = time.time() + seconds
    while time.time() < deadline:
        row = session_row(root, name)
        if row is None or not alive(row):
            return True
        time.sleep(1)
    return False


def session_cwd(root: Path, name: str, sid: str) -> Path:
    """Where the session runs: its listed cwd, else the agent's clone or the orchestrator workspace. Trust is per folder, so this matters."""
    listed = next((r.get("cwd") for r in listed_sessions() if r.get("sessionId") == sid and r.get("cwd")), None)
    if listed:
        return Path(listed)
    agent = next((a for a in load_fleet(root)["agents"] if a["name"] == name), None)
    return repo_dir(root, agent) if agent else root / bus.ORCHESTRATOR


def wake_command(root: Path, name: str, text: str) -> str | None:
    """Re-enter the agent's own session in the background with a new prompt, from its own (trusted) directory."""
    sid = session_id(root, name)
    if not sid:
        return None
    display = shlex.quote(session_name(root, name))  # a resume would otherwise auto-title the session and lose the fleet name
    fleet = load_fleet(root)
    plugin = f" --plugin-dir {shlex.quote(fleet['plugin_dir'])}" if fleet.get("plugin_dir") else ""  # a resume does not re-apply flags: without this the plugin, its hooks and gates are absent
    plugin += shared_flag(root)
    agent = next((a for a in fleet["agents"] if a["name"] == name), None)
    env = " ".join(f"{k}={shlex.quote(v)}" for k, v in (agent_env(root, agent, fleet) if agent else {}).items())  # pinned settings back this up
    prefix = f"{env} " if env else ""
    return f"cd {shlex.quote(str(session_cwd(root, name, sid)))} && {prefix}claude --resume {sid} --bg --name {display}{plugin}{model_flags(fleet, agent)} {shlex.quote(text)}"


def wake_now(root: Path, name: str, text: str) -> bool:
    """The reliable wake: never while busy; stop and wait for the process to die; then resume under the same id."""
    state = session_state(root, name)
    command = wake_command(root, name, text)
    if state in ("busy", "absent") or not command:
        return False
    if state == "idle" and not stop_and_wait(root, name):
        return False
    out = subprocess.run(command, shell=True, capture_output=True, text=True)
    copy = re.search(r"started a copy as ([0-9a-f]+)", out.stderr + out.stdout)
    if copy:  # the original was still alive after all: discard the fork, keep the identity clean
        subprocess.run(["claude", "stop", copy.group(1)], capture_output=True)
        subprocess.run(["claude", "rm", copy.group(1)], capture_output=True)
        return False
    return out.returncode == 0


def under_root(root: Path, cwd: str) -> bool:
    return cwd == str(root) or cwd.startswith(str(root).rstrip("/") + "/")


def prune_victims(root: Path, *, finished: bool) -> list[str]:
    """Sessions of this fleet that are not the recorded real ones; with finished, also the real sessions of done agents. Identity by id, never by title."""
    names = [a["name"] for a in load_fleet(root)["agents"]] + [bus.ORCHESTRATOR]
    owner = {sid: n for n in names for sid in [session_id(root, n)] if sid}  # resolve by name first, so an empty cache never marks live sessions stray
    done = set(waves(root)["done"])
    return [row.get("id") or row["sessionId"][:8] for row in listed_sessions()
            if row.get("sessionId") and under_root(root, row.get("cwd", ""))
            and (row["sessionId"] not in owner or (finished and owner[row["sessionId"]] in done))]


def prune(root: Path, *, finished: bool, run: bool) -> dict:
    """Remove stray copies under the fleet root (sessions that are not the recorded real ones); with finished=True also the real sessions of done agents."""
    victims = prune_victims(root, finished=finished)
    if run:
        for sid in victims:
            subprocess.run(["claude", "stop", sid], capture_output=True)
            subprocess.run(["claude", "rm", sid], capture_output=True)
    return {"pruned" if run else "would_prune": victims}


def shared_flag(root: Path) -> str:
    """Read access to the epic's shared context from any session; writes are still governed by the isolation hook."""
    shared_dir(root).mkdir(exist_ok=True)
    return f" --add-dir {shlex.quote(str(shared_dir(root)))}"


PERMISSION_MODES = {"auto", "acceptEdits", "manual", "dontAsk", "plan"}  # never bypassPermissions: the classifier is the safety net for unattended agents


def model_flags(fleet: dict, agent: dict | None = None) -> str:
    """--model, --effort and --permission-mode for a session: per agent, else per epic; the mode defaults to auto because a
    background session in manual mode waits forever on a prompt nobody sees."""
    chosen = {k: (agent or {}).get(k) or fleet.get(k) or default for k, default in (("model", "sonnet"), ("effort", "low"))}  # speed by default; fleet.json raises it
    mode = (agent or {}).get("permission_mode") or fleet.get("permission_mode") or "auto"
    flags = "".join(f" --{k} {shlex.quote(str(v))}" for k, v in chosen.items() if v)
    return flags + f" --permission-mode {mode if mode in PERMISSION_MODES else 'auto'}"


def start_contract(root: Path, agent: dict, fleet: dict) -> str:
    """Where each start dependency's work is, so the agent builds against it instead of guessing."""
    starts = deps(agent, "start")
    if not starts:
        return ""
    by_name = {a["name"]: a for a in fleet["agents"]}
    named = [f"{d} (PR: {read_status(root, by_name[d])['pr'] or 'see its outbox'}, branch {by_name[d]['branch']}, "
             f"status {read_status(root, by_name[d])['status']})" for d in starts if d in by_name]
    return (" Your start dependencies are at pr-open or done: " + "; ".join(named) + ". Read each PR (gh pr diff <url>) for the contract; "
            f"if one shares your repository, git fetch origin <its branch> and rebase onto it, then onto origin/{fleet.get('base', 'main')} "
            "once it merges; otherwise build against the PR's contract and the artifact it publishes.")


def launch_command(root: Path, agent: dict, fleet: dict) -> str:
    name, epic = agent["name"], fleet["name"]
    workspace, repo = root / name, repo_dir(root, agent)
    base = fleet.get("base", "main")
    push = (f"Pushing this branch to origin ({agent['branch']}) is expected and approved for this epic; never force-push."
            if gates.parse(gates.encode(fleet))["push"] == "auto" else "Never push; the human pushes after review.")
    prompt = (f"You are fleet agent {name} of epic {epic}. First sync: git fetch origin and rebase this branch onto origin/{base} "
              f"(/sdlc:rebase).{start_contract(root, agent, fleet)} {push} Then /sdlc:init, read your fleet inbox (bus.py inbox); then /sdlc:load if .sdlc/context.md exists, "
              f"otherwise read {workspace / 'BRIEF.md'} and start with /sdlc:orient. Read {shared_dir(root)} (the epic's resources: design, spec, contracts, decisions) "
              f"before deciding anything, and ask the orchestrator over the bus to change it. Run /sdlc:save before you stop.")
    session = shlex.quote(f"sdlc/{epic}/{name}")
    plugin = f" --plugin-dir {shlex.quote(fleet['plugin_dir'])}" if fleet.get("plugin_dir") else ""
    env = " ".join(f"{k}={shlex.quote(v)}" for k, v in agent_env(root, agent, fleet).items())
    return f"cd {shlex.quote(str(repo))} && {env} claude --bg --name {session}{plugin}{shared_flag(root)}{model_flags(fleet, agent)} {shlex.quote(prompt)}"


def agent_env(root: Path, agent: dict, fleet: dict) -> dict:
    """Environment every session of this agent runs with: its workspace, the fleet root and epic, and the autopilot switch."""
    extra = {k: str(v) for k, v in fleet.get("env", {}).items()}  # epic-level env, e.g. to scope a personal consent hook
    return {**extra, "SDLC_AGENT_WORKSPACE": str(root / agent["name"]), "SDLC_FLEET_ROOT": str(root), "SDLC_EPIC": fleet["name"],
            "SDLC_AGENT_NAME": agent["name"], "SDLC_GATES": gates.encode(fleet)}


def orchestrator_command(root: Path, fleet: dict) -> str:
    """The orchestrator is a session whose workspace is <root>/orchestrator: it may write only there, and coordinates through fleet.py and bus.py."""
    workspace = root / bus.ORCHESTRATOR
    workspace.mkdir(exist_ok=True)
    env = {**{k: str(v) for k, v in fleet.get("env", {}).items()}, "SDLC_AGENT_WORKSPACE": str(workspace), "SDLC_FLEET_ROOT": str(root),
           "SDLC_EPIC": fleet["name"], "SDLC_AGENT_NAME": bus.ORCHESTRATOR, "SDLC_GATES": gates.encode(fleet)}
    pin_settings(workspace, env, shared_dir(root))  # a wake via --resume does not re-pass inline env; the folder's own settings must carry it
    plugin = f" --plugin-dir {shlex.quote(fleet['plugin_dir'])}" if fleet.get("plugin_dir") else ""
    prompt = (f"You are the orchestrator of epic {fleet['name']} at {root}. You own {shared_dir(root)}, the epic's resources (design, spec, "
              f"contracts, decisions): read it to split the epic, keep it current. Run /sdlc:orchestrate and keep going until every agent is done "
              f"or you are blocked on a human; /sdlc:save before you stop.")
    pairs = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    session = shlex.quote(f"sdlc/{fleet['name']}/orchestrator")
    return f"cd {shlex.quote(str(workspace))} && {pairs} claude --bg --name {session}{plugin}{shared_flag(root)}{model_flags(fleet)} {shlex.quote(prompt)}"


def clone(root: Path, agent: dict, base: str) -> str:
    repo = repo_dir(root, agent)
    if repo.exists():
        return "exists"
    source = agent.get("repo") or agent.get("path")
    subprocess.run(["git", "clone", "--quiet", source, str(repo)], check=True)
    switched = subprocess.run(["git", "-C", str(repo), "switch", "-c", agent["branch"], f"origin/{base}"], capture_output=True)
    if switched.returncode != 0:
        subprocess.run(["git", "-C", str(repo), "switch", "-c", agent["branch"]], capture_output=True)
    return "cloned"


def pin_settings(folder: Path, env: dict, resources: Path) -> None:
    """Every session started in this folder, launched or opened by hand, gets the fleet env, no nested worktree, and read access to resources/."""
    target = folder / ".claude" / "settings.local.json"
    target.parent.mkdir(exist_ok=True)
    current = _load(target, {})
    extra = sorted(set(current.get("permissions", {}).get("additionalDirectories", [])) | {str(resources)})
    target.write_text(json.dumps({**current, "env": {**{k: v for k, v in current.get("env", {}).items() if k != "SDLC_GATES"}, **env},
                                  "worktree": {**current.get("worktree", {}), "bgIsolation": "none"},
                                  "permissions": {**current.get("permissions", {}), "additionalDirectories": extra}}, indent=2) + "\n")


def write_settings(root: Path, agent: dict, fleet: dict) -> None:
    """Pin the agent's workspace in the clone's own .claude/settings.local.json so any session opened there, not only a launched one, is isolated."""
    repo = repo_dir(root, agent)
    if not repo.exists():
        return
    pin_settings(repo, agent_env(root, agent, fleet), shared_dir(root))
    exclude = repo / ".git" / "info" / "exclude"
    if exclude.parent.exists() and ".claude/settings.local.json" not in (exclude.read_text() if exclude.exists() else ""):
        exclude.write_text((exclude.read_text() if exclude.exists() else "").rstrip("\n") + "\n.claude/settings.local.json\n")


SHARED = "resources"
SHARED_README = ("# Resources for this epic\n\nDrop design docs, specs, contracts, meeting notes and external references here. The orchestrator "
                 "reads them to split the epic into agents and keeps them current; every agent reads them before deciding anything. Only the "
                 "orchestrator and the human write here; an agent asks the orchestrator over the bus.\n")
ROOT_GITIGNORE = "# the fleet root versions its definition and resources, never the agent clones\n/*/\n!/resources/\n!/.sdlc/\n/.sdlc/*\n!/.sdlc/fleet.json\n"


def shared_dir(root: Path) -> Path:
    return root / SHARED


def seed_shared(root: Path, fleet: dict, source: Path) -> list[str]:
    """Create <root>/resources (and a root .gitignore) and copy in what fleet.json lists under "resources" (paths relative to the fleet.json); never overwrites."""
    target = shared_dir(root)
    target.mkdir(exist_ok=True)
    for path, text in ((root / ".gitignore", ROOT_GITIGNORE), (target / "README.md", SHARED_README)):
        if not path.exists():
            path.write_text(text)
    copied = []
    for item in fleet.get("resources", fleet.get("shared", [])):
        src = (source / item).resolve()
        dst = target / src.name
        if src.exists() and not dst.exists():
            (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
            copied.append(src.name)
    return copied


def init(fleet_path: Path, root: Path | None = None) -> dict:
    root = (root or fleet_path.resolve().parent).resolve()
    fleet = json.loads(fleet_path.read_text())
    (root / ".sdlc").mkdir(exist_ok=True)
    target = root / ".sdlc" / "fleet.json"
    if fleet_path.resolve() != target.resolve():
        if target.exists() and target.read_text() != fleet_path.read_text():
            shutil.copy(target, target.with_name(f"fleet.{int(time.time())}.json"))  # a re-run never loses the edited definition
        shutil.copy(fleet_path, target)
    seeded = seed_shared(root, fleet, fleet_path.resolve().parent)
    report = {a["name"]: prepare(root, a, fleet) for a in fleet["agents"]}
    trust = [str(repo_dir(root, a)) for a in fleet["agents"] if report[a["name"]] == "cloned"] + [str(root / bus.ORCHESTRATOR), str(shared_dir(root))]  # --add-dir refuses an untrusted folder
    return {"root": str(root), "agents": report, "resources": {"path": str(shared_dir(root)), "seeded": seeded},
            "trust_once": [f"cd {shlex.quote(p)} && claude" for p in trust]}


def prepare(root: Path, agent: dict, fleet: dict) -> str:
    (root / agent["name"]).mkdir(exist_ok=True)
    (root / agent["name"] / "BRIEF.md").write_text(f"# {agent['name']}\n\n{agent.get('brief', '')}\n")
    try:
        outcome = clone(root, agent, fleet.get("base", "main"))
        write_settings(root, agent, fleet)
        return outcome
    except subprocess.CalledProcessError as e:
        return f"clone failed: {e}"


def launch(root: Path, args: list[str]) -> int:
    fleet = load_fleet(root)
    if args[0] == bus.ORCHESTRATOR:
        command = orchestrator_command(root, fleet)
    else:
        command = launch_command(root, next(a for a in fleet["agents"] if a["name"] == args[0]), fleet)
    print(command)
    return subprocess.run(command, shell=True).returncode if "--run" in args else 0


def launched_file(root: Path) -> Path:
    return root / bus.ORCHESTRATOR / "launched.json"


def launch_new(root: Path, ready: list[str], *, run: bool) -> list[str]:
    """Launch READY agents not launched before; the launched set lives in orchestrator/launched.json."""
    fleet, path = load_fleet(root), launched_file(root)
    launched = set(_load(path, []))
    started = [name for name in ready if name not in launched]
    for name in started:
        command = launch_command(root, next(a for a in fleet["agents"] if a["name"] == name), fleet)
        if run:
            subprocess.run(command, shell=True, check=False)
    _store(path, sorted(launched | set(started)))
    return started


def pr_merged(repo: Path, pr: str | None) -> bool | None:
    """GitHub's answer when it can give one: a squash or rebase merge leaves the branch's commits outside origin/<base>."""
    if not pr:
        return None
    try:
        out = subprocess.run(["gh", "pr", "view", pr, "--json", "state", "-q", ".state"], cwd=repo, capture_output=True, text=True)
    except OSError:
        return None
    return out.stdout.strip() == "MERGED" if out.returncode == 0 and out.stdout.strip() else None


def landed(root: Path, name: str) -> bool:
    """True when the agent's branch is already contained in origin/<base>: its PR merged, so its pr-open status is stale."""
    fleet = load_fleet(root)
    agent = next((a for a in fleet["agents"] if a["name"] == name), None)
    repo = repo_dir(root, agent) if agent else None
    if not agent or not repo or not repo.exists():
        return False
    verdict = pr_merged(repo, read_status(root, agent)["pr"])
    if verdict is not None:
        return verdict
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, capture_output=True)
    return subprocess.run(["git", "merge-base", "--is-ancestor", f"origin/{agent['branch']}", f"origin/{fleet.get('base', 'main')}"],
                          cwd=repo, capture_output=True).returncode == 0


def wake_reasons(root: Path, entry: dict) -> list[str]:
    name, reasons = entry["name"], []
    if bus.unread_count(root, name):
        reasons.append("unread fleet messages: run bus.py inbox")
    if entry["status"] == "blocked" and not entry["cannot_land_until"]:
        reasons.append("every merge dependency landed: you may land now")
    if entry["status"] == "pr-open" and landed(root, name):
        reasons.append("your branch is on the base now: /sdlc:load and save **Status**: done")
    return reasons


def wake_waiting(root: Path, current: dict, *, run: bool) -> tuple[list[str], list[str]]:
    """Wake idle agents with unread messages, a landed merge dependency, a landed branch, or a session that stopped mid-brief."""
    woken, stalled = [], []
    for entry in current["running"]:
        name, reasons = entry["name"], wake_reasons(root, entry)
        state = session_state(root, name)
        if entry["status"] == "in-progress" and not reasons and state in ("idle", "stopped"):
            reasons.append("your session stopped with **Status**: in-progress: /sdlc:load and resume, or save **Status**: blocked with the reason")
            stalled.append(name)
        text = "Fleet orchestrator: " + "; ".join(reasons) + ". Then continue your brief and /sdlc:save."
        if reasons and state in ("idle", "stopped") and (wake_now(root, name, text) if run else True):
            woken.append(name)
    return woken, stalled


def base_sha(root: Path, fleet: dict) -> str | None:
    """The base branch's tip as the origin sees it, read from any clone that exists."""
    for agent in fleet["agents"]:
        repo = repo_dir(root, agent)
        if repo.exists():
            out = subprocess.run(["git", "ls-remote", "origin", fleet.get("base", "main")], cwd=repo, capture_output=True, text=True)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.split()[0]
    return None


def base_moved(root: Path, fleet: dict, *, run: bool) -> str | None:
    """When the base advanced (a PR merged), tell every agent to rebase and re-evaluate, and wake the idle ones."""
    marker, now = root / bus.ORCHESTRATOR / "base.sha", base_sha(root, fleet)
    before = marker.read_text().strip() if marker.exists() else None
    if now is None or now == before:
        return None
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(now)
    if before is not None:
        fanout(root, f"base {fleet.get('base', 'main')} moved to {now[:12]}: /sdlc:load (your PR may be merged), then /sdlc:rebase, "
                     "/sdlc:check, and re-read your brief against what landed; /sdlc:save.", run=run)
    return now


def orchestrate(root: Path, *, run: bool) -> dict:
    """One orchestration step: launch the new READY wave, wake agents that are waited on, report the inbox and what to do next."""
    fleet, current = load_fleet(root), waves(root)
    moved = base_moved(root, fleet, run=run)
    started = launch_new(root, current["ready"], run=run)
    woken, stalled = wake_waiting(root, current, run=run)
    finished = len(current["done"]) == len(fleet["agents"])
    pruned = prune(root, finished=finished, run=run)  # copies always; finished agents' sessions once the epic is done
    return {**current, "launched_now": started, "woken": woken, "stalled": stalled, "base_moved_to": moved, **pruned, "messages": bus.inbox(root, bus.ORCHESTRATOR), "epic_done": finished,
            "next": "all agents done: wrap the epic" if finished else "wait for status changes or messages (orchestrate --wait), then run again"}


def snapshot(root: Path) -> str:
    """Comparable view of what the orchestrator waits on: every agent status plus the count of messages."""
    return json.dumps({"status": [read_status(root, a)["status"] for a in load_fleet(root)["agents"]], "messages": len(bus.all_messages(root))})


def wait_for_change(root: Path, seconds: float) -> bool:
    before, deadline = snapshot(root), time.time() + seconds
    while time.time() < deadline:
        time.sleep(5)
        if snapshot(root) != before:
            return True
    return False


def status_report(root: Path) -> dict:
    fleet = load_fleet(root)
    return {"epic": fleet["name"], "agents": [read_status(root, a) for a in fleet["agents"]]}


def up(root: Path, *, run: bool) -> dict:
    """Make sure the orchestrator session exists and is awake: launch it when absent, wake it when idle, leave it when busy."""
    state = session_state(root, bus.ORCHESTRATOR)
    if state == "busy":
        return {"orchestrator": "busy"}
    if state == "absent":
        command = orchestrator_command(root, load_fleet(root))
        if run:
            subprocess.run(command, shell=True, check=False)
        return {"orchestrator": "launched" if run else "absent", "command": command}
    text = "Fleet: run fleet.py orchestrate --run, read your inbox, continue /sdlc:orchestrate."
    return {"orchestrator": state, "woken": wake_now(root, bus.ORCHESTRATOR, text) if run else None}


def fanout(root: Path, text: str, *, run: bool) -> dict:
    """Broadcast from the orchestrator identity, then wake every idle agent so nobody waits for a doorbell."""
    bus.send((root, bus.ORCHESTRATOR), "all", text)
    woken = []
    for agent in load_fleet(root)["agents"]:
        text = "Fleet: new broadcast, run bus.py inbox and act on it, then /sdlc:save."
        if session_state(root, agent["name"]) in ("idle", "stopped") and (wake_now(root, agent["name"], text) if run else True):
            woken.append(agent["name"])
    return {"sent_to": "all", "woken": woken}


def wake(root: Path, args: list[str]) -> int:
    text = " ".join(a for a in args[1:] if a != "--run") or "Fleet: new messages, run bus.py inbox and continue your brief."
    command = wake_command(root, args[0], text)
    print(command or f"no session found named {session_name(root, args[0])}; launch it first")
    if "--run" in args and command:
        return 0 if wake_now(root, args[0], text) else 1
    return 0 if command else 1


def report(root: Path, cmd: str, args: list[str]) -> dict:
    """The JSON-returning commands, keyed by name."""
    run, text = "--run" in args, " ".join(a for a in args if a != "--run")
    if cmd == "orchestrate" and "--wait" in args:
        return {"changed": wait_for_change(root, float(args[args.index("--wait") + 1]))}
    table = {"up": lambda: up(root, run=run), "fanout": lambda: fanout(root, text, run=run), "prune": lambda: prune(root, finished="--done" in args, run=run),
             "orchestrate": lambda: orchestrate(root, run=run), "waves": lambda: waves(root)}
    return table.get(cmd, lambda: status_report(root))()


def view(root: Path, run: bool) -> int:
    """The agent view filtered to this fleet's sessions; prints the command, or opens it with --run."""
    command = ["claude", "agents", "--cwd", str(root)]
    if not run:
        print(" ".join(shlex.quote(c) for c in command))
        return 0
    return subprocess.call(command)


def ide(root: Path, args: list[str]) -> int:
    """Open an agent's own clone (or a file in it) in the IDE: `ide <agent|orchestrator> [file[:line]] [--print]`."""
    fleet = _load(root / ".sdlc" / "fleet.json", {"agents": []})
    name = args[0] if args else ""
    agent = next((a for a in fleet["agents"] if a["name"] == name), None)
    place = repo_dir(root, agent) if agent else root / bus.ORCHESTRATOR if name == bus.ORCHESTRATOR else None
    if place is None:
        print(f"unknown agent {name!r}; one of {[a['name'] for a in fleet['agents']] + [bus.ORCHESTRATOR]}")
        return 2
    rest = [a for a in args[1:] if a != "--print"]
    target = str(place / rest[0]) if rest else str(place)
    return subprocess.call([sys.executable, str(Path(__file__).with_name("ide.py")), target] + [a for a in args[1:] if a == "--print"])


def dispatch(root: Path, cmd: str, args: list[str]) -> int:
    if cmd == "ide":
        return ide(root, args)
    if cmd == "view":
        return view(root, "--run" in args)
    if cmd == "launch":
        return launch(root, args)
    if cmd == "wake":
        return wake(root, args)
    print(json.dumps(report(root, cmd, args), indent=2))
    return 0


def main(argv: list[str]) -> int:
    cmd, args = (argv[0] if argv else "status"), argv[1:]
    if cmd == "init":
        root_arg = Path(args[args.index("--root") + 1]) if "--root" in args else None
        print(json.dumps(init(Path(args[0]), root_arg), indent=2))
        return 0
    root = find_root(Path(os.environ.get("SDLC_FLEET_ROOT") or Path.cwd()))
    if root is None:
        print("no .sdlc/fleet.json found here or above; run: fleet.py init <fleet.json>")
        return 2
    return dispatch(root, cmd, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
