---
name: init
description: Set up sdlc in a repo - detect the stack, write .sdlc/stack.json from a pack, record the base branch, exclude .sdlc from git, optionally start a timebox, then confirm the commands against the repo's own Makefile and CLAUDE.md. Use first in any new repo or timeboxed task.
argument-hint: "[timebox minutes]"
allowed-tools: Read, Edit, Bash(python3:*), Bash(make:*), Bash(git:*), Bash(lsof:*), Bash(podman:*), Bash(pnpm:*)
model: sonnet
effort: low
---
**Already set up** (`.sdlc/stack.json` exists, as on every agent wake): run step 1 only, which refreshes the base, plus the fleet inbox line below; skip steps 2 to 7 and report in one line.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init.py" $ARGUMENTS`. It picks the pack, writes `.sdlc/stack.json` (kept if it already exists), records the base ref, excludes `.sdlc/`, and starts the timebox when minutes are given (a running timebox is kept; `state.py stop` clears it).
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect.py"` and read every CLAUDE.md it lists plus the Makefile targets. Where the repo declares its own command (`make test`, `make typecheck`, a package script), Edit `.sdlc/stack.json` to use it. Repo commands beat pack defaults.
3. Any command copied from repo text (README, CLAUDE.md, Makefile) is shown to the user and confirmed before it is saved: `/sdlc:check` runs stack.json commands in a shell. Mark any command you could not confirm from a file as `"unverified"` in your reply.
4. When the repo has a compose file, a `packageManager` field, or a port the app needs is already listening, read `${CLAUDE_PLUGIN_ROOT}/skills/init/references/local-setup.md` and run its checks: container runtime up, ports free (`lsof -nP -iTCP:<port> -sTCP:LISTEN`), toolchain present. Report what is missing; install nothing without a yes.
5. Run each `check` command once on the untouched base and record green or the exact failing line in `.sdlc/context.md` References, so a pre-existing failure is never mistaken for one the task caused.
6. Set `"ide"` in stack.json only if the user names one.
7. If the repo has no linter config for a language in the pack, mention the fragment in `${CLAUDE_PLUGIN_ROOT}/stacks/lint/<language>/` and its check command. Apply it only when the user says so and owns the repo; never in an timeboxed task repo.

In a fleet session (`SDLC_FLEET_ROOT` set): run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bus.py" inbox` and act on what peers or the orchestrator sent before anything else.

Output, max 10 lines: pack, base ref, the `check` sequence with each command and its baseline result, unverified commands, tools missing, port collisions, timebox.
Next: `/sdlc:orient <area>`.
