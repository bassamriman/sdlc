---
name: step
description: Implement exactly one slice with the smallest diff that turns its failing test green, then stop. Use after red; never for multi-slice work.
argument-hint: "<slice>"
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
model: sonnet
effort: low
---
Rules, in priority order:
1. Smallest diff that passes the slice's test. When `.sdlc/plan.md` exists, touch only its `files:`; if another file is needed, say why first.
2. Write to `/sdlc:standards` as you go: immutable data, parsed types at the edge, ADTs with exhaustive match, no flag booleans, methods of 15 lines or fewer, comments only for a non-obvious why.
3. No refactors outside the slice, no new dependencies without asking.
4. The edit hook reports standards findings and warns when the uncommitted slice passes 120 lines or 6 files; fix findings before continuing and split when warned.
5. Stop after the slice.

Finish by running the slice test, then print: files changed, test result, one line per non-obvious choice.
Next: `/sdlc:why`, then `/sdlc:check`, then commit.
In a fleet session (`SDLC_FLEET_ROOT` set), do not stop here: skip `/sdlc:why` per slice (nobody reads it until review) and go straight to `/sdlc:check` and the commit; `/sdlc:wrap` runs `/sdlc:why` once over the whole branch.
