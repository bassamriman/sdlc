#!/usr/bin/env python3
"""PostToolUse(Bash): after `gh pr create`, record the PR URL in .sdlc/state.json. Fails open."""
from __future__ import annotations

import json
import re
import sys

import notify
import state as st

PR_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")

event = json.load(sys.stdin) if not sys.stdin.isatty() else {}
command = event.get("tool_input", {}).get("command", "")
if re.search(r"\bgh\s+pr\s+create\b", command):
    found = PR_URL.search(json.dumps(event.get("tool_response", "")))
    if found:
        st.main(["state.py", "set", "pr_url", found.group(0)])
        notify.notify(f"pr opened {found.group(0)}")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                 "additionalContext": f"sdlc: recorded PR {found.group(0)}; /sdlc:save before ending."}}))
