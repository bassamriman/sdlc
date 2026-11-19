---
name: par
description: Run independent slices of the current plan in parallel inside one repo - one background agent per slice, each in its own git worktree, results merged by the main session. Use when plan.md has two or more slices that touch disjoint files.
argument-hint: "[slice numbers, default: all independent slices]"
allowed-tools: Read, Agent, Bash(git:*), Bash(python3:*)
model: sonnet
effort: low
---
1. Read `.sdlc/plan.md`. Slices are independent when their `files:` sets do not overlap and neither depends on the other's behaviour. Say which ones qualify; ask before spawning more than three.
2. For each chosen slice spawn one `general-purpose` agent with `isolation: worktree`, run in the background, with this brief: the slice line verbatim, the repo's CLAUDE.md path, "work only on `files:`, follow `/sdlc:red` then `/sdlc:step`, run the slice test, do not commit, report the diff as a patch and the test output". Give it the standards summary from `${CLAUDE_PLUGIN_ROOT}/skills/standards/references/rules.md`. Implementers run on Sonnet like every skill; pass `model: opus` only when the user asks for depth.
3. As each agent finishes, apply its patch on the main branch with `git apply`, run `/sdlc:why` on it, then `/sdlc:check`, then commit. Conflicting patches: apply the smaller first, re-run the other agent with the new base.
4. Never let agents push, message outside the session, or touch files beyond their slice.

Output, max 10 lines: which slices ran, which merged green, which need a rerun. Next: `/sdlc:wrap`.
