---
name: rebase
description: Rebase the current branch onto its moved base safely - preflight, fetch, semantic-conflict preview, rebase --onto, resolve one conflict at a time, recheck, force-with-lease (the push gate asks at that moment). Use when the base branch moved under an open branch or PR.
allowed-tools: Read, Edit, Bash(git:*), Bash(python3:*)
model: sonnet
effort: low
---
Base is `base_ref`/`base_sha` in `.sdlc/state.json`; `<base>` below is `base_ref` with any `origin/` prefix stripped. Run `/sdlc:init` first if absent.

1. Preflight: clean tree (`git status --porcelain` empty), no rebase in progress (`.git/rebase-merge`, `.git/rebase-apply` absent). Otherwise stop and say what to do.
2. `git fetch origin <base branch>`; stop on failure. If `git merge-base --is-ancestor origin/<base> HEAD` succeeds, the branch already contains the base: say "up to date" and stop, with no rebase and no recheck. Preview: `git diff --name-only <base_sha>..HEAD` and `git log --oneline <base_sha>..origin/<base> -- <those files>`; name the files touched on both sides, that is where semantic conflicts hide even when git merges cleanly.
3. `git rebase --onto origin/<base> <base_sha>`. On conflict: `git diff --name-only --diff-filter=U`, show each conflict, resolve it from the slice's intent and continue (`git rebase --continue`); stop and ask only when both sides changed the same behaviour and the intent does not decide it. Always offer `git rebase --abort`; after two rounds of recurring conflicts, abort and suggest squashing first.
4. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" base` to re-record the base, then `/sdlc:check`.
5. `git push --force-with-lease` when the branch was pushed before; the push gate asks at that moment, and the hook denies a bare force-push.

Output, max 8 lines: commits replayed, files touched on both sides, conflicts resolved, check result.
Next: `/sdlc:save`.
In a fleet session, an undecidable conflict goes to the orchestrator in one bus message with both sides; save **Status**: blocked and end the turn.
