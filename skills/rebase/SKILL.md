---
name: rebase
description: Rebase the current branch onto its moved base safely - preflight, fetch, semantic-conflict preview, rebase --onto, resolve one conflict at a time, recheck, force-with-lease on confirmation. Use when the base branch moved under an open branch or PR.
allowed-tools: Read, Edit, Bash(git:*), Bash(python3:*)
model: sonnet
effort: low
---
Base is `base_ref`/`base_sha` in `.sdlc/state.json`; `<base>` below is `base_ref` with any `origin/` prefix stripped. Run `/sdlc:init` first if absent.

1. Preflight: clean tree (`git status --porcelain` empty), no rebase in progress (`.git/rebase-merge`, `.git/rebase-apply` absent). Otherwise stop and say what to do.
2. `git fetch origin <base branch>`; stop on failure. Preview: `git diff --name-only <base_sha>..HEAD` and `git log --oneline <base_sha>..origin/<base> -- <those files>`; name the files touched on both sides, that is where semantic conflicts hide even when git merges cleanly.
3. `git rebase --onto origin/<base> <base_sha>`. On conflict: `git diff --name-only --diff-filter=U`, show each conflict, propose a resolution grounded in the slice's intent, wait, `git rebase --continue`. Always offer `git rebase --abort`; after two rounds of recurring conflicts, abort and suggest squashing first.
4. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" base` to re-record the base, then `/sdlc:check`.
5. Ask, then `git push --force-with-lease` (the hook denies a bare force-push).

Output, max 8 lines: commits replayed, files touched on both sides, conflicts resolved, check result.
Next: `/sdlc:save`.
