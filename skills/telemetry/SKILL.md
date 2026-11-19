---
name: telemetry
description: "/sdlc:telemetry on | off | status - local usage log for reflect. Off by default; stored in the plugin data dir; nothing is transmitted."
argument-hint: "<on | off | status>"
disable-model-invocation: true
allowed-tools: Bash(python3:*)
model: sonnet
effort: low
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/record.py" $ARGUMENTS` and relay the line.

What gets recorded when on, all local, in the plugin data dir: `intent` (your prompt, first 280 chars, harness messages skipped), `skill` (which verb ran, args trimmed, ok/failed), `cmd` (command signature only: binary plus subcommand, no arguments or paths), `scan` (which standards rules fired). Feedback via `/sdlc:feedback` is written regardless, because invoking it is consent.
