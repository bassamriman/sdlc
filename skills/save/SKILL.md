---
name: save
description: Snapshot the working state to .sdlc/context.md so the next session resumes in one line - status, branch, base, PR, progress by slice, decisions, references, open questions, next step. Use before ending a session, after a push or rebase, and before compaction.
allowed-tools: Read, Write, Bash(git:*), Bash(python3:*)
model: sonnet
effort: low
---
Gather: `git log --oneline -1`, `git status --porcelain`, `.sdlc/state.json` (base, pr_url, timebox), `.sdlc/plan.md`.

Overwrite `.sdlc/context.md`, hard cap 40 lines:
```
# Saved context
**Status**: not-started | in-progress | blocked | pr-open | done
**Branch**: <branch> at <sha>   **Base**: <base_ref>   **PR**: <url or none>
**Uncommitted**: <count or none>
**Next**: <the single next command, e.g. /sdlc:red "Slice 3">
## Progress
- Done: slices ...
- In progress: slice N, failing test <name>
- Remaining: ...
## Decisions
- <decision> because <why>
## References
- path:line - why it matters
## Open questions
- ...
```
Keep the `**Key**: value` lines exactly in that shape; the session hook reads them. Replace, never append: done slices collapse to one line, answered questions and superseded decisions are deleted, references only for files still in play. The file is reloaded in full every session, so every line costs context. Say what you wrote in one line.
