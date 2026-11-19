#!/usr/bin/env python3
"""Aggregate the usage and feedback logs into the facts /sdlc:reflect reasons from. Prints JSON, never edits anything."""
from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter

import record

TAIL, TOP, REPEAT_SECONDS = 5000, 15, 120


def read(log: str) -> list[dict]:
    try:
        lines = (record.data_dir() / f"{log}.jsonl").read_text().splitlines()[-TAIL:]
    except OSError:
        return []
    return [json.loads(line) for line in lines if line.strip()]


def seconds_between(a: dict, b: dict) -> float:
    return (dt.datetime.fromisoformat(b["ts"]) - dt.datetime.fromisoformat(a["ts"])).total_seconds()


def unresolved_intents(rows: list[dict]) -> list[str]:
    found = []
    for i, row in enumerate(rows):
        following = [r["kind"] for r in rows[i + 1:i + 4]]
        if row["kind"] == "intent" and "skill" not in following:
            found.append(row["text"][:120])
    return found[-TOP:]


def sequences(rows: list[dict]) -> Counter:
    skills = [r["skill"] for r in rows if r["kind"] == "skill" and r.get("skill")]
    return Counter(f"{a} > {b}" for a, b in zip(skills, skills[1:]) if a != b)


def repeats(rows: list[dict]) -> Counter:
    skills = [r for r in rows if r["kind"] == "skill"]
    return Counter(b["skill"] for a, b in zip(skills, skills[1:]) if a["skill"] == b["skill"] and seconds_between(a, b) < REPEAT_SECONDS)


def summary(rows: list[dict], feedback: list[dict]) -> dict:
    return {
        "window": {"records": len(rows), "from": rows[0]["ts"] if rows else None, "to": rows[-1]["ts"] if rows else None},
        "skills": Counter(r["skill"] for r in rows if r["kind"] == "skill").most_common(TOP),
        "skill_failures": Counter(r["skill"] for r in rows if r["kind"] == "skill" and r.get("ok") is False).most_common(TOP),
        "sequences": sequences(rows).most_common(TOP),
        "repeats_within_2min": repeats(rows).most_common(TOP),
        "commands": Counter(r["sig"] for r in rows if r["kind"] == "cmd").most_common(TOP),
        "intents_without_skill": unresolved_intents(rows),
        "scan_rules": Counter(rule for r in rows if r["kind"] == "scan" for rule in r.get("rules", [])).most_common(TOP),
        "feedback": [{"ts": f["ts"], "about": f.get("about"), "text": f["text"]} for f in feedback[-TOP:]],
    }


def main() -> int:
    rows, feedback = read("usage"), read("feedback")
    if not rows and not feedback:
        print(json.dumps({"insufficient_data": True, "hint": "python3 record.py on, then use the plugin for a while"}))
        return 0
    print(json.dumps(summary(rows, feedback), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
