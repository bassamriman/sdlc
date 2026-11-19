---
name: orient
description: Map an unfamiliar repo or area before touching it - entry points, data model, existing tests and patterns, unknowns. Use at the start of a task or when entering new code.
argument-hint: "<feature or area, one line>"
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*)
model: sonnet
effort: low
---
Read-only. Set the phase: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" phase orient`.

Read the project's CLAUDE.md/README first, then the model, API and test files nearest `$ARGUMENTS`. For a broad sweep, delegate to the built-in `Explore` agent and keep only its conclusion.

Output, hard cap 15 lines:
- Entry points and the files the feature will touch.
- Data model in one line per entity.
- Existing test style and fixtures to reuse.
- 3 unknowns, each phrased as a question.
- 2-3 observations about the code (bugs, risks), stated but not fixed.

Verify two of your own claims by reading the code before reporting them.
When a timebox runs or the area has a request flow worth showing, finish with `/sdlc:diagram sequence <area>` in brief mode (two diagrams, three ranked pitfalls, three summary lines).
Next: `/sdlc:clarify <requirement>` when the ask is ambiguous or modifies data, else `/sdlc:plan <feature>`.
