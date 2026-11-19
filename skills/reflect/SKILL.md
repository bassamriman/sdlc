---
name: reflect
description: Mine the local usage and feedback logs and propose concrete changes to this plugin - a new verb for a repeated manual command, a changed default, a dead verb to delete, a scan rule to tune. Proposes only; a human approves; never edits the plugin. Use monthly or when the tooling feels off.
argument-hint: "[focus, e.g. a verb or rule]"
allowed-tools: Bash(python3:*), Read
model: sonnet
effort: low
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reflect.py"` and reason from its JSON only; do not read the raw logs. If it says insufficient data, say so and stop. Also suggest the user runs `/skill-doctor` for the built-in context-cost view; do not duplicate it.

Pattern to mechanic:
- feedback entry: top of the list, verbatim, with the change it implies.
- a command signature repeated with no skill around it: propose a new verb (name, 3-line spec).
- an intent with no skill following: a discoverability gap; propose a description change on the nearest verb.
- a skill repeated within two minutes: it fails or under-delivers; propose the fix.
- a frequent A > B sequence: propose chaining B into A's `Next:`.
- a scan rule firing far more than the others: suspect noise; propose a precision change, with examples to collect.
- a verb never used in the window: propose deleting it.

Output, hard cap 12 lines: ranked proposals, each `evidence (counts) - change (file) - confidence strong|weak`. Scope to `$ARGUMENTS` when given. End by asking which proposal to draft; draft only on a yes, as a diff for review, never applied.
