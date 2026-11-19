#!/usr/bin/env python3
"""Per-epic human gates, read from SDLC_GATES ("push=auto,pr=auto,message=auto,commit=check"). Unset means every gate on."""
from __future__ import annotations

import os

DEFAULTS = {"commit": "check", "push": "ask", "pr": "ask", "message": "ask", "branch_delete": "ask", "diagram": "off"}
STRICT = {**DEFAULTS, "diagram": "require"}  # a misspelled value tightens to the strictest choice
AUTOPILOT = {**DEFAULTS, "push": "auto", "pr": "auto", "message": "auto", "branch_delete": "auto"}
VALUES = {"commit": {"check", "off"}, "push": {"ask", "auto"}, "pr": {"ask", "auto"}, "message": {"ask", "auto"},
          "branch_delete": {"ask", "auto"}, "diagram": {"off", "require"}}


def parse(spec: str) -> dict:
    """Unknown keys and values fall back to the default: a typo must tighten, never loosen."""
    chosen = dict(pair.split("=", 1) for pair in spec.split(",") if "=" in pair)
    return {k: chosen[k] if chosen.get(k) in VALUES[k] else (STRICT[k] if k in chosen else v) for k, v in DEFAULTS.items()}


def current() -> dict:
    return parse(os.environ.get("SDLC_GATES", ""))


def encode(fleet: dict) -> str:
    base = AUTOPILOT if fleet.get("autopilot") else DEFAULTS
    return ",".join(f"{k}={v}" for k, v in parse(",".join(f"{k}={v}" for k, v in {**base, **fleet.get("gates", {})}.items())).items())


UNATTENDED = {"auto", "dontAsk", "bypassPermissions"}


def decision(mode: str | None, wanted: str) -> str:
    """In a mode nobody watches, a question would park the agent forever: it becomes a denial with the reason, never a prompt."""
    return "deny" if wanted == "ask" and mode in UNATTENDED else wanted


def reason(mode: str | None, wanted: str, text: str) -> str:
    return text + "; nobody answers prompts in this mode, so it is denied: adapt, or message the orchestrator or the human" if decision(mode, wanted) != wanted else text
