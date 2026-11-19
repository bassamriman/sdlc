---
name: check
description: Evidence gate - run the stack's test, typecheck and lint sequence and unblock the commit only when the exact working tree is green. Use before every commit and before claiming anything is done.
allowed-tools: Bash(python3:*), Read
model: sonnet
effort: low
---
Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check.py"` and report its output verbatim. It stops at the first failure and records the working tree on success; the commit hook compares that record.

Rules:
- No "done", "fixed" or "passing" claim without this run's output in the same message.
- On FAIL: show the failing command and the relevant lines, fix the cause, rerun. Never weaken a test or silence a check to get green. If the cause is unclear after one look, `/sdlc:debug`.
- `SKIP` means the pack has no command for that step; say so. `RED: nothing ran` means stack.json is empty: fill it.

Next: commit (`git commit`), or `/sdlc:wrap` when the task is done.
- `no .sdlc/stack.json` or `malformed .sdlc/stack.json` (exit 2) means the gate could not run: do what the line says (`/sdlc:init`, or fix the JSON), then rerun. Do not commit.
