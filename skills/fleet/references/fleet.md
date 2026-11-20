# fleet.json

Lives at `<root>/.sdlc/fleet.json` (or anywhere; `init` copies it there). `<root>` holds one folder per agent.

```json
{
  "name": "payments-v2",
  "base": "main",
  "model": "sonnet",
  "effort": "medium",
  "agents": [
    { "name": "contracts", "repo": "git@github.com:org/contracts.git", "branch": "feat/payments-v2",
      "brief": "Add the PaymentIntent schema and publish the client." },
    { "name": "api", "repo": "git@github.com:org/api.git", "branch": "feat/payments-v2",
      "brief": "Expose POST /payments using the new contract.",
      "depends": [ { "on": "contracts", "phase": "start" } ] },
    { "name": "web", "path": "/Users/me/src/web", "branch": "feat/payments-v2",
      "brief": "Payment form against POST /payments.",
      "depends": [ { "on": "api", "phase": "merge" } ] }
  ]
}
```

- `repo` is cloned; `path` clones from a local checkout instead (its `origin` is that checkout, so agents push a branch back to it).
- Optional top-level `plugin_dir`: launched sessions get `--plugin-dir <path>`, for running the plugin from source.
- `phase: start`: the agent cannot begin until the dependency's status is `pr-open` or `done`; its launch prompt names each start dependency's PR and branch, so same-repo agents rebase onto that branch (then onto `origin/<base>` after it merges) and cross-repo agents read the PR for the contract.
- `phase: merge`: the agent may build now but cannot land until the dependency is `done`.
- Status per agent comes from `<root>/<agent>/<repo>/.sdlc/context.md` (`**Status**` line written by `/sdlc:save`) and the PR URL from `state.json`. Values: `not-started`, `in-progress`, `blocked`, `pr-open`, `done`, or `no-workspace` before `init`.
- Launch: `cd <repo> && SDLC_AGENT_WORKSPACE=<root>/<agent> claude --bg --name sdlc/<epic>/<agent> "<prompt>"`.
- A fresh clone is an untrusted folder: `claude --bg` refuses it ("Workspace not trusted") until the human runs `claude` there once interactively and accepts the trust prompt. `fleet init` cannot do this for them; say so after cloning.

`SendMessage` between sessions is a best-effort doorbell only; the bus file is the record and `wake` is the reliable channel.
- `init` also writes `<clone>/.claude/settings.local.json` with `env.SDLC_AGENT_WORKSPACE` and `env.SDLC_FLEET_ROOT` (excluded from git), so a session opened by hand in the clone is isolated too, not only a launched one.
- Sessions record their cwd: `claude agents --cwd <root>` lists only the fleet's sessions. `init` sets `worktree.bgIsolation: none` in each clone's local settings: the clone is the isolation, and a nested worktree would hide `.sdlc/` from `fleet status` and push to a `worktree-*` branch.
- Human gates are per epic, top-level `"gates"`: `commit` (`check`, the default: a green `/sdlc:check` on the exact tree; or `off`), `push`, `pr`, `message` (to `sdlc/<epic>/*` peers only), `branch_delete` (each `ask`, the default, or `auto`). `"autopilot": true` is shorthand for every gate `auto` with `commit=check`; a `gates` entry overrides it. Sessions receive the result as `SDLC_GATES` plus `SDLC_EPIC`; an unknown key or value falls back to the default, so a typo tightens, never loosens. Never relaxed: the bare force-push denial and workspace isolation. Leave gates on for epics you review by hand, such as the plugin improving itself.
- Optional top-level `"env"`: extra variables every session of the epic receives, in the launch command and the clone settings. Use it to scope a personal hook, e.g. `{"GIT_CONSENT_GROUPS": "none"}` when a user-level consent hook would otherwise prompt inside an autopilot epic.

## Orchestrator and the bus
- `fleet.py launch orchestrator --run` starts `sdlc/<epic>/orchestrator`, a session whose workspace is `<root>/orchestrator/` (its own context.md, fleet.json draft, outbox). It runs `/sdlc:orchestrate`.
- `fleet.py orchestrate [--run]` is one step: launch every READY agent not yet launched (tracked in `orchestrator/launched.json`), report waves, the orchestrator's inbox and `epic_done`. `--wait <seconds>` blocks until any agent status or the message count changes; for a human watching in the foreground only, never inside the orchestrator session, which is woken by hooks.
- Bus: `bus.py send <agent|all|orchestrator> <text>` appends to the sender's own `<root>/<name>/outbox.jsonl`; `bus.py inbox` lists unread messages to me or to all from every peer's outbox and advances `inbox.cursor`; `bus.py peek` counts them. Identity comes from `SDLC_AGENT_NAME`/`SDLC_AGENT_WORKSPACE` and `SDLC_FLEET_ROOT`. Writing only one's own outbox keeps isolation intact; the session hook shows the unread count at start. `send` also prints the native `SendMessage` doorbells (one per recipient session, a pointer to the outbox, no payload) so a recipient is woken rather than left polling; the file is the record, the doorbell is best-effort.
- Agents read the bus at `init` and `load`, the session hook shows the unread count at start, and a prompt hook (`bus.py nudge`) prints a one-line reminder on every turn while messages wait. So a message is seen within one turn even if its doorbell was missed.

## Waking sessions reliably
- `claude --bg` assigns session ids itself (it ignores `--session-id`), so the fleet finds each session by its name `sdlc/<epic>/<agent>` in `claude agents --json` and caches the id in `orchestrator/sessions.json`. `fleet.py wake <agent> [text] --run` never wakes a busy session; for an idle one it runs `claude stop <id>`, waits until the listed pid is dead (resuming a live process forks a copy), then `claude --resume <id> --bg "<text>"` from the session's own directory, which continues the same session.
- `orchestrate` wakes, on every step, each idle agent that has unread messages or whose last merge dependency landed; a busy agent is left to the `SendMessage` doorbell it will see on its next turn (`bus.py nudge`). Idle is read from `claude agents --json`.
- Saved context stays small: `save` rewrites `.sdlc/context.md` under 40 lines and prunes; the session hook warns past 60.
- `fleet.py up --run` keeps the orchestrator present: launches `sdlc/<epic>/orchestrator` when absent, wakes it when idle. `fleet.py fanout "<text>" --run` broadcasts to every agent as the orchestrator and wakes the idle ones.
- Agents report mechanically: a hook posts the `**Status**` and `**PR**` lines to the orchestrator's inbox whenever `.sdlc/context.md` is written, and `gh pr create` posts the PR URL; both wake an idle orchestrator. Status is still derived from each context.md; the message is the doorbell that keeps tracking current.

## Many agents on one repository (e.g. a fork with ten briefs)
Every agent lists the same `repo` and its own `branch` and `brief`; each gets its own clone, so ten agents never share a checkout. `init` prints `trust_once`: one `cd <clone> && claude` per clone, the only manual step. The orchestrator watches the base branch on every step: when a PR you merged moves `origin/<base>`, it broadcasts "base moved: load, rebase, check, re-read your brief" and wakes every idle agent; an agent whose PR merged sees it in `/sdlc:load` and saves `done`.

## Diagram of the diff on every commit
`gates.diagram: require` makes the commit hook refuse a source commit without an updated `docs/arch/<branch>.md`. `python3 "$PLUGIN/scripts/archdiff.py"` generates it: a Mermaid graph of the changed files (highlighted, with +/- counts) and the modules they import, from the recorded base. GitHub renders it in the PR. `/sdlc:diagram` can refine it by hand.
- `fleet.py prune [--done] --run` stops and removes stray copies under the fleet root (sessions not in `orchestrator/sessions.json`); with `--done`, also the sessions of agents whose status is `done`. `orchestrate` prunes copies on every step and finished sessions once `epic_done`.
- Telemetry and the `telemetry.on` marker live in one place, `~/.local/share/sdlc` (`SDLC_DATA_DIR` overrides), for hooks, the Bash tool and the shell alike.
- A resume re-applies no flags: `wake` passes `--name` and `--plugin-dir` again, otherwise the resumed session runs without the plugin, its hooks and its gates.
- If a resume still reports "started a copy", `wake` stops and removes that copy and reports the wake as failed, so a copy never takes over an agent's name. `claude stop`/`rm` take the short id.
- Optional `model` and `effort` (top-level for the epic, overridable per agent) are passed as `--model`/`--effort` at launch and on every wake; unset means `sonnet` and `low`, for speed. Ten agents on `sonnet` at `low` effort cost a fraction of ten at the session default.

## Resources
`<root>/resources/` is the epic's drop zone and ground truth: design docs, specs, contracts, decisions, meeting notes, external references. Drop files there before defining agents; `/sdlc:orchestrate` reads it to split the epic and can be re-run as it grows. `init` creates it, plus a root `.gitignore` that versions `resources/` and `.sdlc/fleet.json` and ignores the clones, and copies in what `fleet.json` lists under `"resources": ["docs/design.md", "contracts/"]` (relative to the fleet.json, never overwritten). Every session gets read access: `--add-dir` at launch and wake, and `permissions.additionalDirectories` in each clone's and the orchestrator's `.claude/settings.local.json`, so a session opened by hand sees it too (Claude Code refuses `--add-dir` on an untrusted folder, so `resources/` is in the `trust_once` list with the clones and the orchestrator); each reads it before deciding anything. A re-run of `init` keeps the previous `.sdlc/fleet.json` as `fleet.<time>.json`. Only the orchestrator and the human write it; agents are read-only there and ask the orchestrator over the bus. Nothing in the fleet ever deletes it.
- The isolation hook denies any write to `.claude/settings*.json` or `.git/`, any write into the plugin, and any command that sets an `SDLC_*` variable, even inside the workspace. Identity on the bus is `SDLC_AGENT_NAME` (else the workspace basename); the sender of a message is the folder its outbox lives in; `bus.py log` lists every message without moving a cursor. `orchestrate` also reports `stalled`: agents saved in-progress whose session is idle or stopped, woken once per step.
- Optional `permission_mode` (top-level or per agent): `auto` by default, also `acceptEdits`, `manual`, `dontAsk`, `plan`; passed as `--permission-mode` on launch and wake. A background session in manual mode stops at the first prompt with nobody to answer it. `bypassPermissions` is never passed; an unknown value falls back to `auto`.
- In auto mode the guard's gates (push, pr, message, branch_delete) still prompt: the agent pauses, shows as waiting in `claude agents`, and the human approves in that session. Isolation never prompts there: a write outside the clone is denied with the reason.
- `fleet.py retire <agent> [--run]` ends a done agent's session and removes it from the agent view; the clone stays unless `--delete-clone`, which refuses while there are uncommitted files or commits on no remote branch. The agent stays in `fleet.json` so dependents still see it as done; `--force` retires an agent that is not done.
