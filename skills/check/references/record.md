# The design record

Every commit message and every PR description carries the same three sections. The commit gate refuses a commit
without them (`gates.record`, on by default); a commit that changes source must also update `docs/design/<branch>.md`.

## Commit message

```
<imperative subject under 72 characters>

Assumptions:
- <each assumption this change relies on, from .sdlc/assumptions.md; or: none>
Design: docs/design/<branch>.md
Pitfalls:
- fixed: <hazard> at <file:line>
- deferred: <hazard>, because <reason>
```

`Pitfalls:` with `- none` is fine when none were found. Never write "none" for assumptions you made but did not list.

## docs/design/<branch>.md

Mermaid diagrams of what the branch touches, kept current with every commit (`/sdlc:diagram` with no type, `--keep`):
- **Entities** when models, migrations or schema change.
- **Flow**: a sequence of each changed call path, with its failure paths (timeout, retry, duplicate).
- **State** when a status or lifecycle changes.
- **API**: each endpoint added or changed, with its request and response shape and error codes.
A changed existing diagram is drawn before and after. Hazards are marked where they happen, and a `Pitfalls` table
lists each with `file:line`, fixed or deferred, verified or inferred.

## PR description

`## Summary`, `## Assumptions`, `## Diagrams` (the diagrams from `docs/design/<branch>.md`, inline),
`## Pitfalls` (two lists: fixed in this PR, deferred with the reason), `## How to test`, `## Risks and trade-offs`,
`## Open questions`. Empty sections are omitted, except Assumptions and Pitfalls, which say "none".
