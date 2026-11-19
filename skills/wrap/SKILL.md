---
name: wrap
description: Finish - run the evidence gate, get an independent review of the whole diff, simplify, and produce the 60-second summary (what, why, trade-offs, next) plus the commit message. Use at the end of a task or in the last 10 minutes of a timebox.
allowed-tools: Read, Edit, Bash(git:*), Bash(python3:*), Agent
model: sonnet
effort: low
---
Set the phase: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" phase wrap`.

1. `/sdlc:check`; do not continue on red.
2. Read `git diff <base_sha from .sdlc/state.json>` once end to end. Delete dead code and stray debug output.
3. `/sdlc:review` on the same range (fan-out per lens, large diffs split by directory; one reviewer, standards+arch, while a timebox runs). Fix BLOCKER and MAJOR findings; list MINOR ones as follow-ups.
4. Run `/simplify` if installed, then `/sdlc:check` again if anything changed.
5. List untested branches in the diff, max 3 lines.

Output, hard cap 10 lines:
- What changed and why, in two sentences; if a brief-mode diagram exists, say which of its pitfalls you fixed and which you left, and why.
- Two trade-offs you chose and what you gave up.
- What you deliberately did not do.
- Next steps, max 3.
- Commit message for whatever is still uncommitted: imperative subject under 72 characters; body only for a non-obvious why. If every slice is already committed, say so instead.
Next: commit, then `/sdlc:pr open` when a PR is wanted, then `/sdlc:save`.
