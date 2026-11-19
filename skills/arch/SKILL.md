---
name: arch
description: Architecture review of a design or diff - failure modes, idempotency, ordering, consistency, deadlines and retries, backpressure, p99 and fan-out, data growth, authz boundary, cost. Use for any design decision, new endpoint with writes, or before shipping.
argument-hint: "[design text, file or diff, default: working tree vs the recorded base]"
allowed-tools: Read, Grep, Glob, Bash(git:*)
model: sonnet
effort: low
---
Load `${CLAUDE_PLUGIN_ROOT}/skills/arch/references/lens.md` (18 questions) and `${CLAUDE_PLUGIN_ROOT}/skills/arch/references/p99.md` (cause to fix); when the change touches models, migrations, queries or transactions, also `${CLAUDE_PLUGIN_ROOT}/skills/arch/references/db.md` (transactions, isolation, locks, constraints, indexes, online migrations). Apply only the questions the change can trigger; skip the rest silently.

Procedure:
1. Input: `$ARGUMENTS` if given, else `git diff <base_sha from .sdlc/state.json>`, else `git diff HEAD`.
2. Find the touched seams: network call, queue, write path, migration, cache, authz check, loop over data.
3. Answer the matching lens questions from the code, citing `file:line`. If the code cannot answer, that is the finding.
4. p99: name the likely tail source and the cheapest fix. N parallel calls at p99 give `1-(0.99)^N` slow requests.
5. Questions marked S need system context: answer them when it is at hand, else list them as follow-ups, not blockers. 11 is a D question when the diff shows a migration or a shape change.

Output, hard cap 12 lines: ranked risks (`file:line - risk - fix`), a recommend/avoid verdict, follow-ups. For a decision worth recording use `engineering:architecture` (ADR) or `engineering:system-design` if installed; for a picture, `/sdlc:diagram`.
Next: fix the ranked risks, `/sdlc:check`, then commit or `/sdlc:wrap`.
