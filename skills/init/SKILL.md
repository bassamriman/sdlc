---
name: init
description: Set up sdlc in a repo - detect the stack, write .sdlc/stack.json from a pack, record the base branch, exclude .sdlc from git, optionally start a timebox, then confirm the commands against the repo's own Makefile and CLAUDE.md. Use first in any new repo or timeboxed task.
argument-hint: "[timebox minutes]"
allowed-tools: Read, Edit, Bash(python3:*), Bash(make:*), Bash(git:*)
model: sonnet
effort: low
---
1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init.py" $ARGUMENTS`. It picks the pack, writes `.sdlc/stack.json` (kept if it already exists), records the base ref, excludes `.sdlc/`, and starts the timebox when minutes are given (a running timebox is kept; `state.py stop` clears it).
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect.py"` and read every CLAUDE.md it lists plus the Makefile targets. Where the repo declares its own command (`make test`, `make typecheck`, a package script), Edit `.sdlc/stack.json` to use it. Repo commands beat pack defaults.
3. Any command copied from repo text (README, CLAUDE.md, Makefile) is shown to the user and confirmed before it is saved: `/sdlc:check` runs stack.json commands in a shell. Do not run the test suite now. Mark any command you could not confirm from a file as `"unverified"` in your reply.
4. Set `"ide"` in stack.json only if the user names one.
5. If the repo has no linter config for a language in the pack, mention the fragment in `${CLAUDE_PLUGIN_ROOT}/stacks/lint/<language>/` and its check command. Apply it only when the user says so and owns the repo; never in an timeboxed task repo.

In a fleet session (`SDLC_FLEET_ROOT` set): run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bus.py" inbox` and act on what peers or the orchestrator sent before anything else.

Output, max 8 lines: pack, base ref, the `check` sequence with each command, unverified commands, tools missing, timebox.
Next: `/sdlc:orient <area>`.
