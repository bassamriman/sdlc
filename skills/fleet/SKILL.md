---
name: fleet
description: "/sdlc:fleet init <fleet.json> | status | run | launch <agent> - multi-repo epics with one isolated Claude session per agent: clones a workspace per agent, computes READY and BLOCKED waves from the dependency graph and saved contexts, launches ready agents as named background sessions. Run from the human's session; it clones repos and starts sessions."
argument-hint: "<init <fleet.json> | status | run | launch <agent>>"
disable-model-invocation: true
allowed-tools: Read, Write, Bash(python3:*), Bash(git:*), Bash(claude:*), Bash(cd:*)
model: sonnet
effort: low
---
Script: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fleet.py"`. Definition format and an example: `${CLAUDE_PLUGIN_ROOT}/skills/fleet/references/fleet.md`.

- **init <fleet.json>**: creates `<root>/<agent>/` with a `BRIEF.md` and a clone on the agent's branch; idempotent. The approved `fleet.json` is the go-ahead; clone without asking again. A new clone must be trusted once (the human, or their auto-trust job) before a launch works.
- **status**: one line per agent from its own `.sdlc/context.md` and `state.json`. Status is read, never asked for over messages.
- **run**: `fleet.py waves`, then run `launch <agent> --run` for each READY agent; the approved split is the go-ahead, so no second confirmation. Each session is named `sdlc/<epic>/<agent>` and starts with `/sdlc:rebase` onto the base, `/sdlc:init`, `bus.py inbox`, then `/sdlc:load` if a saved context exists, otherwise the brief via `/sdlc:orient`. BLOCKED agents are listed with what they wait on; RUNNING ones with what they cannot land until.
- **launch <agent>**: one agent, the same way.

Inside an agent session `SDLC_AGENT_WORKSPACE` is set: the hook denies edits outside the workspace and gates `SendMessage` per the epic. To talk to a peer or the orchestrator: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/bus.py" send <agent|all|orchestrator> <text>` writes your outbox and prints the `SendMessage` doorbells to ring next; `bus.py inbox` reads yours. Message only what the graph cannot see; status is derived from saved contexts. `/sdlc:orchestrate` runs the epic from the orchestrator session (`launch orchestrator`). Re-enter a stopped agent with `claude --resume`.

Output, max 12 lines. Next: `fleet status` after agents report `pr-open`, then `/sdlc:pr address` inside each agent.
