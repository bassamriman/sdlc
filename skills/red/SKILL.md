---
name: red
description: Write the failing test for the current slice, run it, and show it failing for the right reason. Use at the start of each slice, before implementing.
argument-hint: "<slice from plan>"
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
model: sonnet
effort: low
---

1. State the test names and the expected values in plain words first, so the human can correct them. Expectations are the human's call; you fill the bodies.
2. Reuse existing fixtures and factories; follow the repo's test style.
3. Run the test using `commands.test` from `.sdlc/stack.json`, scoped to the new test.
4. Confirm it fails for the intended reason (missing behaviour), not an import or setup error. If not, fix the test.

Cover the slice's happy path plus the one edge case most likely to be wrong. Output: test diff and the failure line, nothing else. For larger test design use `engineering:testing-strategy` if installed.
Next: `/sdlc:step <slice>`.
In a fleet session (`SDLC_FLEET_ROOT` set), do not stop here: run the `Next:` step yourself.
