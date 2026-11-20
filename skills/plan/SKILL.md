---
name: plan
description: Write a short slice plan - ordered vertical slices, each with its test, files and verify command, plus an out-of-scope list. Skip for changes under about 20 lines. Use after clarify.
argument-hint: "<clarified spec>"
allowed-tools: Read, Grep, Glob, Write, Bash(python3:*)
model: sonnet
effort: low
---

When the design has real options and no timebox is running (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" show` has no `budget_min`), ask the built-in `Plan` agent for two alternatives and recommend one with the trade-off in a sentence; under a timebox pick one yourself and state the trade-off in a sentence. Use `engineering:architecture` only when the decision deserves an ADR.

Write `.sdlc/plan.md`, hard cap 10 lines, one slice per line in exactly this shape (the edit hook parses `files:`):
```
- Slice 1: <behaviour> | test: <test name> | files: app/api.py, app/models.py | verify: <command>
- Out of scope: <what you are deliberately skipping>
- Risks: <at most 2>
```
Rules: smallest working slice first, thin end-to-end before polish, each slice fits a diff under 60 lines, a data-model change is its own slice with a migration check. Say which slice is the "thin version" to have working by 57% of the timebox.
Next: `/sdlc:red <slice 1>`.
