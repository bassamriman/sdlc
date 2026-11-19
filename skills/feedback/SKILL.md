---
name: feedback
description: Record a note about the plugin itself - a verb that annoyed you, a rule that misfired, a step you keep doing by hand - so reflect can act on it later. Use whenever the user comments on the tooling rather than the code.
argument-hint: "<text> [about: verb or rule]"
allowed-tools: Bash(python3:*)
model: sonnet
effort: low
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/record.py" feedback "<text>" [about]`, quoting the user's words verbatim, not a paraphrase. If the note names a verb or a scan rule, pass it as `about`. Reply with one line.
