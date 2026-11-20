---
name: sessions
description: Show the agent view filtered to this fleet's sessions, open an agent's clone in the IDE, or retire a finished agent - prints the `claude agents --cwd <root>` command, or lists the sessions with their status and state. Use when asked to see, watch, list, open or clean up the fleet's agents or sessions.
argument-hint: "[fleet root] [ide <agent> [file[:line]] | retire <agent> [--delete-clone]]"
allowed-tools: Bash(python3:*), Bash(claude agents:*)
model: sonnet
effort: low
---
1. Root: `$ARGUMENTS`, else `$SDLC_FLEET_ROOT`, else the current fleet (`.sdlc/fleet.json` above the cwd).
2. Print the command for the user to run in their own terminal (the interactive view needs a terminal): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fleet.py" view` from the root.
3. Then list the sessions here: `claude agents --json --all --cwd <root>`, one line each: agent name (last path part), status, state. Flag any `blocked` or `failed` one and say what to run (`fleet.py wake <agent> --run`, or `/sdlc:orchestrate`).
4. `ide <agent> [file[:line]]`: open that agent's own clone (or a file in it) in the IDE: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fleet.py" ide <agent> [file[:line]]` from the root; `orchestrator` opens the orchestrator's folder.
5. `retire <agent> [--delete-clone]`: show `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/fleet.py" retire <agent>` (dry run) from the root, get a yes, then rerun with `--run`. It ends the session and keeps the clone unless `--delete-clone`, which refuses while anything is unpushed; an agent not `done` needs `--force`, which only the human asks for.
