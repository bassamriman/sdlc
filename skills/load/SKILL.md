---
name: load
description: Resume from .sdlc/context.md - verify the branch, fast-forward from origin, re-read the files changed since the base, and emit the one next command. Use at the start of a session that continues earlier work.
allowed-tools: Read, Grep, Bash(git:*), Bash(python3:*)
model: sonnet
effort: low
---
1. Read `.sdlc/context.md`; if absent, say so and suggest `/sdlc:orient`.
2. Verify: current branch equals **Branch**; `git status --porcelain` matches **Uncommitted**. Differences are reported, never auto-fixed.
3. `git fetch origin` then `git merge --ff-only @{upstream}` when an upstream exists; on divergence stop and suggest `git pull --rebase` or `/sdlc:rebase`. If the base moved (`git log --oneline <base_sha>..origin/<base>` non-empty), say so.
4. Read every file in `git diff --name-only <base_sha>` so the slice context is live, not remembered.
5. If **PR** is set: `gh pr view --json state,reviewDecision` and report in one line.

Output, max 8 lines: status, what changed since the snapshot, then exactly one next command (from **Next**, adjusted if step 3 or 5 changed the picture).
In a fleet session (`SDLC_FLEET_ROOT` set): run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bus.py" inbox` and act on what peers or the orchestrator sent before anything else.
