---
name: debug
description: Systematic debugging when a test or command fails for an unclear reason - reproduce, read the whole error, one hypothesis at a time, smallest experiment, fix, regression test. Use when check or a test fails and the cause is not obvious in one look.
argument-hint: "<failing command or error>"
allowed-tools: Read, Grep, Glob, Edit, Bash
model: sonnet
effort: low
---
If `engineering:debug` is installed, use it with this input and apply only the rules below that it lacks. Otherwise:

1. Reproduce with the exact command; paste the full error, not the last line.
2. State one hypothesis and the single cheapest experiment that would refute it. Run it. No shotgun edits, no "try this too".
3. Repeat at most three times. After three refuted hypotheses, stop and report what is known; ask the user.
4. Fix the root cause in the smallest diff, then Grep for the same construct elsewhere: a bug found once is usually written twice. If the cause was a missing case, add it as a regression test first (`/sdlc:red` shape).
5. Say in one line why it failed and why the fix is the right level (not a symptom patch).

Timebox: 10 minutes under a timebox; past that, revert to the last green tree and ship the thin version.
Next: `/sdlc:check`.
