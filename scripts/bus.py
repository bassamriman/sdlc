#!/usr/bin/env python3
"""Message bus for a fleet: every session appends only to its own outbox (<root>/<name>/outbox.jsonl) and reads its peers'
outboxes read-only, so messaging never needs an exception to workspace isolation. CLI: send <to|all> <text> | inbox [--all] | peek | log (every message in the fleet)."""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

ORCHESTRATOR = "orchestrator"


def identity() -> tuple[Path, str]:
    """(fleet root, my name): SDLC_AGENT_NAME when the launcher set it, else the workspace basename; neither means the orchestrator."""
    root = Path(os.environ["SDLC_FLEET_ROOT"])
    workspace = os.environ.get("SDLC_AGENT_WORKSPACE")
    return root, os.environ.get("SDLC_AGENT_NAME") or (Path(workspace).name if workspace else ORCHESTRATOR)


def outbox(root: Path, name: str) -> Path:
    return root / name / "outbox.jsonl"


def send(who: tuple[Path, str], to: str, text: str) -> dict:
    root, me = who
    path = outbox(root, me)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "from": me, "to": to, "text": text}
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def doorbells(root: Path, record: dict) -> list[dict]:
    """Native SendMessage calls the sender should make next: one per recipient session, pointing at the outbox, never carrying the payload."""
    epic = os.environ.get("SDLC_EPIC", "")
    fleet = json.loads((root / ".sdlc" / "fleet.json").read_text()) if (root / ".sdlc" / "fleet.json").exists() else {"agents": []}
    gone = set(json.loads((root / ORCHESTRATOR / "retired.json").read_text())) if (root / ORCHESTRATOR / "retired.json").exists() else set()
    names = [a["name"] for a in fleet["agents"] if a["name"] not in gone] + [ORCHESTRATOR] if record["to"] == "all" else [record["to"]]
    note = f"fleet bus: new message from {record['from']} in {outbox(root, record['from'])}; run bus.py inbox"
    return [{"to": f"sdlc/{epic}/{n}", "message": note} for n in names if n != record["from"]]


def _rows(p: Path) -> list:
    out = []
    for line in p.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # a concurrent append can leave a partial last line
    return out


def all_messages(root: Path) -> list[dict]:
    """Every message in the fleet; the sender is the folder the outbox lives in, never the field a writer claims."""
    rows = [dict(r, **{"from": p.parent.name}) for p in sorted(root.glob("*/outbox.jsonl")) for r in _rows(p) if isinstance(r, dict) and "ts" in r]
    return sorted(rows, key=lambda r: r["ts"])


def inbox(root: Path, me: str, *, unread_only: bool = True) -> list[dict]:
    """Messages addressed to me or to all, newer than my cursor; reading advances the cursor."""
    cursor = root / me / "inbox.cursor"
    since = cursor.read_text().strip() if cursor.exists() else ""
    mine = [r for r in all_messages(root) if r["from"] != me and r["to"] in (me, "all") and (not unread_only or r["ts"] > since)]
    if mine and unread_only:
        cursor.parent.mkdir(parents=True, exist_ok=True)
        cursor.write_text(mine[-1]["ts"])
    return mine


def unread_count(root: Path, me: str) -> int:
    cursor = root / me / "inbox.cursor"
    since = cursor.read_text().strip() if cursor.exists() else ""
    return sum(1 for r in all_messages(root) if r["from"] != me and r["to"] in (me, "all") and r["ts"] > since)


def nudge() -> int:
    """UserPromptSubmit hook: one line when unread messages wait; silent outside a fleet session or when there are none."""
    if not os.environ.get("SDLC_FLEET_ROOT"):
        return 0
    root, me = identity()
    rows = inbox(root, me, unread_only=True)  # reading marks them read, so the agent never has to call inbox itself
    for r in rows[-10:]:
        print(f"[fleet bus] {r['from']} -> {r['to']}: {r['text']}")
    if len(rows) > 10:
        print(f"[fleet bus] {len(rows) - 10} older unread message(s): bus.py inbox --all")
    return 0


def show(rows: list[dict]) -> None:
    for r in rows:
        print(f"[{r['ts']}] {r['from']} -> {r['to']}: {r['text']}")


def main(argv: list[str]) -> int:
    if argv and argv[0] == "nudge":
        return nudge()
    root, me = identity()
    cmd = argv[0] if argv else "inbox"
    commands = {
        "send": lambda: (print(json.dumps(sent(root, me, argv), indent=2)), wake_recipient(argv[1])) if len(argv) >= 3 else None,
        "peek": lambda: print(unread_count(root, me)),
        "log": lambda: show(all_messages(root)),
        "inbox": lambda: show(inbox(root, me, unread_only="--all" not in argv)),
    }
    if cmd not in commands or (cmd == "send" and len(argv) < 3):
        return usage(cmd)
    commands[cmd]()
    return 0


def wake_recipient(to: str) -> None:
    """A message to the orchestrator wakes it when idle, so delivery never depends on the sender also ringing it."""
    if to in (ORCHESTRATOR, "all") and os.environ.get("SDLC_AGENT_NAME") != ORCHESTRATOR:
        import notify  # lazy: notify imports this module
        notify.wake_orchestrator(Path(os.environ.get("SDLC_FLEET_ROOT", ".")))


def usage(cmd: str) -> int:
    print(f"unknown command {cmd!r}; use send <to> <text> | inbox [--all] | peek | log", file=sys.stderr)
    return 2


def sent(root: Path, me: str, argv: list[str]) -> dict:
    record = send((root, me), argv[1], " ".join(argv[2:]))
    return {"sent": record, "notify_with_SendMessage": doorbells(root, record)}

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
