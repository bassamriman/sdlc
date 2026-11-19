---
name: pr
description: Pull request lifecycle with gh - open a draft PR with a concise description and a diagram per kind of change (API, entities, flow, state machine), address review comments and red checks, view the PR in Chrome, or finish after merge. Use after wrap when a PR is wanted, when a PR has review comments or red checks, to look at it in the browser, or once it merged.
argument-hint: "<open [--ready] | address | view [files|checks|commits] | done>"
allowed-tools: Read, Write, Edit, Bash(gh:*), Bash(git:*), Bash(python3:*), Bash(open:*)
model: sonnet
effort: low
---
Branch is the current branch; base is `base_ref` in `.sdlc/state.json` with any `origin/` prefix stripped. Everything that reaches GitHub is confirmed with the user first.

**open**: `gh pr view --json number,url` first; if a PR exists, report it (`--ready` turns a draft ready after confirmation). Else write `.sdlc/pr-body.md`, short enough to read in a minute:
- `## Summary` (from `/sdlc:wrap`, two sentences), `## How to test`, `## Risks and trade-offs`, `## Open questions` (omit empty sections; no file list, the PR shows it).
- `## Diagrams`: classify `git diff <base_sha>` by kind and draw only the kinds it touches, from the code, as `/sdlc:diagram` does: **API** (routes, handlers, request and response schemas: endpoints with their shapes), **Entities** (models, migrations, ORM or schema files: ER), **Flow** (a new or changed call path across modules or services: sequence with failure paths), **State machine** (status enums, transition tables, `match` on a status: states and transitions). A changed existing one is drawn before and after, changed parts styled. Hazards marked in place with a short `Pitfalls` table (file:line, fix, verified or inferred) as `/sdlc:diagram` step 5-6 does; a pitfall the PR fixes shows in the before, one it introduces is a review finding, not a footnote. At most four diagrams, each under about 15 nodes.
Show title and body, wait for yes, then `gh pr create --draft --title "<imperative, under 72 chars>" --body-file .sdlc/pr-body.md --base <base> --head <branch>` (`--ready` drops `--draft`). Draft by default so nobody is pinged by accident. The hook records the URL.

**address**: `gh pr view --json number,state,reviewDecision,reviews,comments,statusCheckRollup` and `gh api repos/{owner}/{repo}/pulls/{n}/comments` for inline threads. MERGED or CLOSED: report and stop. A hard red check: `gh pr checks --json name,state,link`, then `gh run view <run id> --log-failed | tail -80`; match the failing job to a `commands.*` entry in `.sdlc/stack.json` and `/sdlc:debug` that command with the log first. Triage every comment as **blocker** (correctness, security, explicit must-fix), **nit** (cheap style) or **question** (needs the human's decision); skip `[bot]` logins. Print the list, wait. Apply blockers and nits as one slice (`/sdlc:check` before commit; a finding is a pattern, fix every site), draft replies for questions. Show every reply with the reviewer's login, wait, then post: inline threads with `gh api repos/{owner}/{repo}/pulls/{n}/comments/{id}/replies -f body=...`, conversation comments with `gh pr comment <n> --body "@<login> ..."` quoting the point answered. Push only through the normal gate.

**view [files|checks|commits]**: `url=$(gh pr view --json url -q .url)` (no PR: say so, suggest `open`); append `/files`, `/checks` or `/commits` when asked; then `open -a "Google Chrome" "$url"`, falling back to `gh pr view --web` if Chrome is not installed. Read-only; report the URL in one line.

**done**: `gh pr view --json state -q .state`; not MERGED: say so and stop. Else `git switch <base> && git pull --ff-only`, `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" unset pr_url`, `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" stop`, then offer `git branch -d <branch>` (the guard asks).

Output, max 10 lines (the body is a file, not output). Next: `/sdlc:save`; after a push, `/sdlc:rebase` if the base moved; once merged, `/sdlc:pr done`.
