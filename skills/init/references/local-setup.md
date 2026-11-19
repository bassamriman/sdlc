# Local setup

Read when `init` finds a container file (`docker-compose.yml`, `compose.yaml`, a `Dockerfile`), a `packageManager` field, or a port the app needs is busy. Every item ends in a check the agent can run.

## Container runtime: Podman as Docker
- `docker compose ...` from a README runs on Podman with two pieces: a compose provider (`brew install podman-compose`; `podman compose version` names it) and `alias docker=podman` in the user's shell config. The alias lives in interactive shells only; scripts and the Bash tool call `podman compose` directly.
- The Podman VM stops on reboot. `podman machine list` shows it; `podman machine start` brings it back. "Cannot connect to Podman" or an ssh handshake reset means the VM is down.
- Check: `podman compose version && podman ps`.

## Many instances of one compose app
- Each instance gets its own checkout: compose apps usually bind-mount `./backend` and `./frontend`, and a SQLite file lives inside the mount, so two instances on one folder share code and data. Use `git worktree add ../<name> -b <branch>`.
- Compose names the project after the folder, so containers, networks and volumes are separate per checkout. Services reach each other by service name inside their own project; only host ports collide.
- Host ports: make the left side of each mapping a variable with the original as default, `"${BACKEND_PORT:-8000}:8000"`, then `BACKEND_PORT=8001 FRONTEND_PORT=5174 podman compose up --build -d`. The edit is local tooling: keep it out of the feature diff (`git stash` before the task, or `git update-index --skip-worktree docker-compose.yml`) and mention it rather than commit it.
- Check: `podman ps --format '{{.Names}} {{.Ports}}'`.

## Busy ports and `localhost`
- `localhost` resolves to `::1` first on macOS. A dev server bound to `[::1]:5173` (Vite's default) answers `localhost:5173` while a container publishes `*:5173`, so the browser shows another app with no error. `127.0.0.1:<port>` always reaches the container.
- Check: `lsof -nP -iTCP:<port> -sTCP:LISTEN` lists every listener; two lines means a collision. Name the owning process and ask before stopping it.

## Node and pnpm
- Node 25 and later ship without `corepack`. `brew install pnpm` gives a launcher that reads `packageManager` in `package.json` and runs that exact pnpm version, matching a container that pins it.
- A host `node_modules` and the container's `node_modules` volume are separate; installing on the host leaves the container untouched.
- nvm config that sources a missing `nvm.sh` fails silently; `type nvm` tells. `node` then comes from Homebrew.
- A solution-style `tsconfig.json` (`"files": []` plus `references`) is checked with `tsc -b`; plain `tsc --noEmit` checks only the root.
- Check: `pnpm --dir frontend install --frozen-lockfile && pnpm --dir frontend run lint`.

## Baseline before the first edit
Run every `check` command on the untouched base and record the result in `.sdlc/context.md` under References, one line each: green, or the exact failing line. A failure present on the base is reported as pre-existing and left alone; fixing it is an unrelated change in the diff unless the user asks for it.
