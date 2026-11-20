---
name: review
description: Fan-out review of a diff - independent reviewer agents per lens (standards, architecture, p99, database, tests and operability, security), local lenses sliced by directory on big diffs, every finding adversarially refuted before anything is fixed; collapses to one fast reviewer while a timebox runs. Use from wrap, before a PR, or when a diff is too big for one read.
argument-hint: "[range or files] [--lenses standards,arch,p99,db,tests,security] [--full]"
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*), Agent
model: sonnet
effort: low
---
Range: `$ARGUMENTS` if given, else `git diff <base_sha from .sdlc/state.json>`, else `git diff HEAD`. Lenses default to all six (db only when the diff touches models, migrations, queries or transactions); `--lenses` narrows.

**Timebox running** (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" show` has `budget_min`) and no `--full`: one `sdlc:reviewer` agent, lenses standards+arch, whole diff, then one refuter over its findings. Say in one line that the review was narrowed.

**Otherwise, fan out:**
1. `git diff --stat <range>`. Local lenses (standards, tests, security) get sliced: up to 12 files one slice, else one slice per top-level directory, small ones merged, at most 6. Cross-file lenses (arch, p99, db) always get the whole diff: their findings are about interactions.
2. Spawn one `sdlc:reviewer` per lens x slice, all in a single message so they run concurrently (never one after another), read-only, with the range, the file list, the lens name and its reference: standards -> `${CLAUDE_PLUGIN_ROOT}/skills/standards/references/rules.md` plus the language file; arch -> `${CLAUDE_PLUGIN_ROOT}/skills/arch/references/lens.md`; p99 -> `${CLAUDE_PLUGIN_ROOT}/skills/arch/references/p99.md`; db -> `${CLAUDE_PLUGIN_ROOT}/skills/arch/references/db.md`; tests -> "untested branches, missing failure-path tests, order-dependent or flaky tests, names that do not state behaviour"; security -> "injection, authz at the boundary, secrets or PII in logs, unbounded input, SSRF, path traversal". Every lens runs on Sonnet at low effort (the reviewer agent's setting); pass `model: opus` on the Agent call for arch, p99 and the refuter only when the user asks for depth over speed. Each returns at most 10 lines `SEVERITY - file:line - finding - fix`.
3. Merge: same `file:line` and same gist from two lenses count once, tagged with both; drop anything without `file:line`; sort BLOCKER, MAJOR, MINOR.
4. **Refute every finding, always.** One refuter agent per lens that reported anything, all in one message so they run concurrently, none given the original reviewer's reasoning: "for each finding, read the cited code and try to prove it wrong (the path cannot happen, the guard exists elsewhere, the cost is bounded, it predates this diff); default to refuted when uncertain". Refuted findings are dropped and listed separately with the reason; a finding that predates the diff is kept only as a labelled follow-up. Never skip this step, whatever the severity mix.
5. Sweep: a finding is a pattern, not a line. For each surviving BLOCKER or MAJOR derive the search (the construct, API or name involved) and Grep the whole repo, not only the diff; sibling sites join the same finding as extra `file:line`s. Fix all sites or none, never one.
6. Apply surviving BLOCKERs and MAJORs only when asked or when called from `/sdlc:wrap`; otherwise present the list.

Output, max 15 lines: lens x slice matrix (agents run, findings each, refuted count), then the merged list. Next: fix, `/sdlc:check`, then `/sdlc:wrap` or `/sdlc:pr open`.
