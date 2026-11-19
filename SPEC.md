# sdlc: specification

## Goal
A Claude Code plugin for the software development lifecycle: a single-agent loop, review lenses (architecture, tail latency, database, coding standard), plus resumable context, the PR lifecycle, opt-in telemetry with a reflect loop, and a multi-agent fleet layer with an orchestrator that stays dormant in single-repo work.

## Design constraints
1. Few words per verb: every SKILL.md under 30 lines, hard output caps, detail in `references/`.
2. The human stays in control: small diffs, `why` after any diff, expectations set by the human in `red`; gates per epic decide what an agent may do without a human.
3. Core never hard-codes a tool: skills read `.sdlc/stack.json`; `init` prefers repo-declared commands and confirms any command copied from repo text.
4. Tiny changes skip the plan. No mandatory phases. The fleet layer is inert unless `SDLC_AGENT_WORKSPACE` or `.sdlc/fleet.json` exists.
5. Evidence gate: no "done" claim without a fresh `check`; the commit hook enforces it on the exact working tree and fails closed.
6. Only `gh` for GitHub, only when a PR is requested; no named MCP servers.
7. Reuse platform primitives (`Agent` with worktree isolation, `SendMessage`, `/simplify`, `/code-review`, artifacts) instead of rebuilding them.
8. Every hook script runs on Python 3.9+, because a hook that cannot start is a hook that is silently off.
9. Hooks and scripts enforce isolation, gates, status reporting, waking.

## Review lenses
- standards: 24 rules tagged H (hook, all languages), HP (hook, Python), L (stack linter, fragments shipped), J (judgement); each with a one-line why.
- arch: 18 questions, each marked D (answerable from the diff) or S (needs system context), each with a one-line why; p99 cause-to-fix list; a 16-question database lens (transactions, isolation anomalies, locks, constraints, indexes, query shape, online and reversible migrations, backfills, retries, idempotent writes, types, replicas, connections, plans). The lens is for daily review; a timebox only narrows it to the D questions the change touches.

## Fleet and orchestration
One clone and one named background session per agent; waves from start and merge edges; status derived from each agent's saved context and reported by hooks; a file bus (outbox per session) with native doorbells; deterministic wakes (`claude stop`, wait for the process, `--resume --bg` with name and plugin re-applied); an orchestrator session with its own workspace; per-epic gates, env, model and effort; a diagram of the diff per commit when required.

## Acceptance
`claude plugin validate` passes; `python3 -m unittest discover -s tests` passes under Python 3.9 and 3.14; the plugin's own scripts pass the plugin's scan; `scripts/e2e.py` (single-agent loop) and `scripts/e2e_fleet.py run` (orchestrated three-agent epic) pass all their checks unattended.

## Known limits
- Skill auto-triggering and `SendMessage` as a sole channel are untested; the bus and the resume are the reliable paths.
- The agent view may drop finished sessions from its listing; the fleet keeps session ids by name and resumes them regardless.
- Trust records and bulk session removal are the human's actions (the `cd <clone> && claude` lines `fleet init` prints as `trust_once`, and `python3 scripts/fleet.py prune --run` from a shell).
