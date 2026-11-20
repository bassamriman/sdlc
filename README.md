# sdlc

A Claude Code plugin for the software development lifecycle: planning, test-first slices, checks, review, diagrams, pull requests, rebasing and multi-agent fleets. Hooks enforce the gates and workspace isolation. Design notes: [SPEC.md](SPEC.md).

## Install (local)
From the root of this checkout:
```
claude plugin marketplace add "$(pwd)"
claude plugin install sdlc@sdlc-local
```
Session-only: `claude --plugin-dir "$(pwd)"`, then `/reload-plugins` after edits. Hooks need any `python3` 3.9 or newer on PATH (the macOS system Python qualifies). Tests: `python3 -m unittest discover -s tests` (hook scripts are tested by piping JSON; the suite also compiles every script with an older interpreter when one is installed).

## Quick start
**Single task** (in the repo, with the plugin loaded):
```
/sdlc:init                # detect stack, record base (add minutes for an optional timer)
/sdlc:orient <area>       # map the code; ends with a brief-mode diagram and three ranked pitfalls
/sdlc:clarify <ask>       # assumptions and questions, pitfalls turned into questions
/sdlc:plan <feature>      # slices with test, files, verify
/sdlc:red <slice>         # failing test, then /sdlc:step, /sdlc:why, /sdlc:check, commit; repeat
/sdlc:wrap                # gate, fan-out review, 60-second summary
/sdlc:pr open             # concise body with diagrams per kind of change; later: address, view, done
```
`/sdlc:diagram <type> <subject> --show` opens a diagram in Chrome.

**Fleet of agents on one epic:** quickest start: `mkdir <root> && cd <root> && python3 ~/dev/sdlc/scripts/fleet.py up --run`, then give the orchestrator the repo and the goal; it drafts the split, you approve, it clones and launches. Or by hand:
1. Write `fleet.json` (agents, branches, briefs, `start`/`merge` dependencies, `gates`, `model`, `effort`); format in `skills/fleet/references/fleet.md`.
2. `python3 scripts/fleet.py init fleet.json`, then trust each clone once with the `cd <clone> && claude` lines it prints. Drop design docs into `<root>/resources/`.
3. `python3 scripts/fleet.py up --run` starts the orchestrator session; it launches waves, answers agents over the bus and wakes them. You merge PRs; agents rebase on their own.
4. Watch: `claude agents --cwd <root>`, `SDLC_FLEET_ROOT=<root> python3 scripts/bus.py log`, `python3 scripts/fleet.py status`.

## Verbs
| Layer | Verb | Does | Cap |
|---|---|---|---|
| core loop | `init [minutes]` | detect stack, write `.sdlc/stack.json`, record base, start timebox | 8 lines |
| | `orient <area>` | map entry points, data model, tests, unknowns | 15 |
| | `clarify <req>` | assumptions, edge cases, questions; data-modification rules | 8 bullets |
| | `plan <spec>` | slices with test, files, verify; parseable by the hook; skip under ~20 lines | 10 |
| | `red <slice>` | failing test, human sets expectations | diff + failure line |
| | `step <slice>` | smallest green diff, then stop | files + result |
| | `why [file\|range]` | line-by-line rationale, guesses marked, 2 quiz questions | 12 |
| | `check` | evidence gate: test, typecheck, lint; unblocks commit | script output |
| | `debug <error>` | reproduce, one hypothesis at a time, regression test | 10 min under a timebox |
| | `wrap` | gate, review, simplify, 60-second summary, commit message | 10 |
| review | `review [range] [--lenses standards,arch,p99,db,tests,security] [--full]` | fan-out: one reviewer agent per lens (standards, arch, p99, db, tests, security), big diffs split by directory, findings merged | 15 |
| | `standards [file\|range]` | 24-rule coding standard, judgement rules only, confidence 80+ | 10 |
| | `arch [design\|file\|range]` | 18-question architecture lens + p99 checklist + 16-question database lens (transactions, isolation, locks, constraints, indexes, online migrations) | 12 |
| | `diagram <er\|sequence\|flow\|state\|modules> <subject\|path> [--keep] [--show]` | Mermaid er/sequence/flow/state/modules of the current code, hazards (N+1, app-side filtering, missing transaction, missing index, ...) marked in place with a verified/inferred pitfalls table; under a timebox, brief mode (two diagrams, three ranked pitfalls, three summary lines); `--show` renders locally in Chrome | file |
| ship | `pr open [--ready] \| address \| view [files\|checks\|commits] \| done` | draft PR with a concise body and a diagram per kind of change; triage and answer review comments and red checks; view in Chrome; after merge: back to the base, clear the PR and timebox | 10 |
| | `rebase` | preflight, semantic-conflict preview, `--onto`, recheck, `--force-with-lease` | 8 |
| resume | `save` / `load` | `.sdlc/context.md` snapshot; session hook digests it on start | 40 / 8 |
| tooling | `ide [file[:line]] [--print]` | PyCharm, IDEA, GoLand, RustRover, WebStorm, VS Code, Cursor by stack | 1 |
| self-improvement | `telemetry on\|off\|status` · `feedback <text> [about]` · `reflect [focus]` | opt-in local log; reflect proposes plugin changes, never edits | 12 |
| multi-agent | `fleet init <fleet.json> \| status \| run \| launch <agent>` | one isolated named session per agent, waves from the dependency graph | 12 |
| | `orchestrate [design]` | orchestrator session: split a design into agents with a dependency graph, write fleet.json, launch READY waves, answer agents over the bus, keep `resources/` current, finish when every agent is done | 12 |
| | `sessions [fleet root] [ide <agent> [file[:line]] \| retire <agent> [--delete-clone]]` | the agent view filtered to the fleet: prints `claude agents --cwd <root>` and lists each session's status, flagging blocked or failed ones | 10 |
| | `par [slice numbers]` | independent slices in parallel worktrees inside one repo | 10 |

Defaults: a range or file defaults to the working tree against the recorded base; `--keep` writes the diagram to `docs/design/` instead of the untracked `.sdlc/design/`; `--show` renders it in Chrome; `--full` forces the fan-out review even under a timebox; `--ready` opens the PR ready instead of draft; `--print` shows the IDE command without running it.

**Scripts** (run from the shell; skills call the same ones):
| Script | Parameters |
|---|---|
| `fleet.py` | `init <fleet.json> [--root <dir>]`, `status`, `view [--run]`, `ide <agent|orchestrator> [file[:line]] [--print]`, `waves`, `launch <agent\|orchestrator> [--run]`, `up [--run]`, `fanout <text> [--run]`, `wake <agent> [text] [--run]`, `orchestrate [--run] [--wait <seconds>]`, `prune [--done] [--run]`, `retire <agent> [--force] [--delete-clone] [--run]`; without `--run` each prints what it would do |
| `bus.py` | `send <agent\|all\|orchestrator> <text>`, `inbox [--all]`, `peek`, `log` |
| `archdiff.py` | `[base] [--print]` for the diff; `--repo [path] [--depth N] [--print]` for the current module map (depth 0 = one node per file) |
| `render.py` | `<file.md> [--print]` renders Mermaid to a local page and opens it |
| `state.py` | `start <minutes>`, `stop`, `phase <name>`, `base`, `set <key> <value>`, `unset <key>`, `show` |
| `record.py` | `on`, `off`, `status`, `feedback <text> [about]` |
| `e2e.py` / `e2e_fleet.py` | `setup`, `wait`, `verify` / `run [plugin_dir] [minutes]`, `verify` |

## Hooks (runtime, not prompts)
- **Edit/Write scan**: every language: history comments, TODO without ticket, commented-out code, comment density. Python: methods over 15 lines, over 3 params, bool params, mutable defaults, bare except. Plus: slice over 120 lines or 6 files (docs and tests excluded), edit outside `plan.md` files, secret literals. `SDLC_SCAN=off` disables.
- **Bash guard**: `git commit` blocked until `/sdlc:check` is green on that exact working tree (index-insensitive; files over 2 MB are tracked by size and mtime). The commit check runs before anything else in the command, so `git commit && git push` cannot slip through. `git push`, `gh pr create` and `branch -d` ask; bare force-push denied (`--force-with-lease` allowed). Fails closed: a crash exits 2 and `onFailure: block` covers timeouts. `SDLC_GATE=off` disables.
- **Fleet isolation** (only when `SDLC_AGENT_WORKSPACE` is set): edits outside the workspace or the session scratchpad denied; Bash commands that write or change git state outside it (absolute or relative paths) ask; writes into the plugin, to `.claude/settings*.json` or `.git/`, and `SDLC_*` overrides are denied; `SendMessage` asks unless the epic's message gate is auto. In auto mode gate prompts (push, PR, message, branch delete) still appear for a human attached to the session; isolation outside the clone is denied without a prompt. A repo that has `.sdlc/` but no `stack.json` is a closed gate (run `/sdlc:init`); a crash in either hook exits 2.
- **Gates per epic** (`fleet.json` `gates`, delivered as `SDLC_GATES`): `commit` check or off; `push`, `pr` (create or merge), `message`, `branch_delete` (local `branch -d`, remote `push --delete` or `:ref`) ask or auto; `diagram` off or require (require makes the commit hook refuse a source commit without an updated `docs/arch/<branch>.md`). A misspelled value tightens, never loosens. `autopilot: true` sets all auto with the commit check kept, so sessions of one epic can talk, commit and push unattended. Bare force-push stays denied. Every skill and the reviewer run on Sonnet at low effort for speed, and fleet sessions default to the same; per epic or per agent, `model` and `effort` in `fleet.json` raise it.
- **Self-tests**: `python3 scripts/e2e.py setup && python3 scripts/e2e.py wait && python3 scripts/e2e.py verify` (one agent through the whole loop) and `python3 scripts/e2e_fleet.py run` (three agents under the orchestrator, eight checks). Both keep their fixture repos under the data dir (`SDLC_DATA_DIR` or `~/.local/share/sdlc`).
- Skill `allowed-tools` pre-approves tools, it never restricts them: read-only verbs (`orient`, `clarify`, `standards`, `arch`) are read-only by instruction, not by hook.
- **Session start**: verbs, pack, base, plan progress, saved-context digest, timebox. **Prompt**: timebox line (silent after 2x budget). **PreCompact**: tells compaction what to preserve. **After `gh pr create`**: records the PR URL.
- **Telemetry** (off by default, local only): intent, skill, command signature, scan rules.

## Stacks
`stacks/*.json`: marker groups, commands, check order, languages. Packs: generic, python, python-django-react, typescript, scala-sbt, java-gradle, java-maven, kotlin-gradle, go, rust. Detection prefers packs whose markers sit at the repo root, so a vendored `go.mod` does not outrank the real stack. `init` prefers the repo's own Makefile and CLAUDE.md commands, and asks before saving any command copied from repo text because `check` runs them in a shell. Each pack's `notes` says what its lint command enforces vacuously until the linter is wired. `stacks/lint/<language>/` holds verified linter fragments that enforce the standard mechanically; `stacks/lint/README.md` lists what each tool cannot enforce.

## Reuses Claude built-ins when present
`Explore` and `Plan` agents, `/simplify`, `/code-review`, `/security-review`, `/skill-doctor`, `Agent` with `isolation: worktree`, `ListAgents`/`SendMessage`, the Artifact tool with `artifact-diagramming`; `engineering:*` plugin skills when installed. Everything degrades to the plugin's own steps when absent.

## Verified and not
Hooks are tested by piping JSON under Python 3.9 and 3.14. The single-agent loop and an orchestrated three-agent epic run unattended as self-tests (`scripts/e2e.py`, `scripts/e2e_fleet.py run`). Background-session facts the fleet layer is built around: `claude --bg` assigns ids itself (found by name, cached); the agent view can drop finished sessions while their conversations remain resumable; `claude stop`/`rm` take the short id; a resume re-applies no flags, so `wake` passes `--name` and `--plugin-dir`; resuming a live process forks a copy, which `wake` prevents and discards. Untested: skill auto-triggering and `SendMessage` as the only channel. Pack commands are defaults `init` replaces from the repo. Scan limits: trailing inline comments and Python docstrings are not scanned; a nested function's lines count toward its parent.
