---
name: run
description: Boot the app from this repo's own clone and prove it is up - find how the repo runs (Makefile, compose, package scripts, CLAUDE.md), start it in the background, wait until healthy, list the URLs, and optionally smoke-test the UI and API pages. Use when asked to boot, start, run or open the service, or to check what still blocks it from starting.
argument-hint: "[--smoke] [--stop]"
allowed-tools: Read, Grep, Glob, Bash
model: sonnet
effort: low
---
1. **How it runs:** read the repo's CLAUDE.md, README and Makefile (`up`, `run`, `dev`, `start`, `serve` targets) and any compose file; prefer the repo's own documented command, and its parallel-instance or slot mechanism when it has one, so this clone never collides with another clone's stack.
2. **Blockers first:** ports the app needs already listening (`lsof -nP -iTCP:<port> -sTCP:LISTEN`, and which folder or container holds them), missing tools, missing env files, a database to seed. Report each with the one command that clears it; stop a stack only when it is this clone's own.
3. **Start** in the background from this clone, never from another one; wait for health (poll each URL with `curl -s -o /dev/null -w "%{http_code}" -m 3` until 2xx or 3xx, at most 2 minutes); on failure show the last 30 log lines and the cause.
4. Report: one line per service with its URL and status; the command to stop it.
5. `--smoke`: open the UI URL in Chrome (`open -a "Google Chrome" <url>`, or the Chrome tools when present: load the page, read console errors), and GET each API page the repo documents (README endpoint table, `/api/docs`, `/openapi.json`) reporting the status code and time; never send a write request.
6. `--stop`: stop only what this clone started (its compose project or the process it launched).

Output, max 10 lines: services with URLs and status, blockers cleared or remaining, smoke results, stop command.
