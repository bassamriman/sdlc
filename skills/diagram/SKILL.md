---
name: diagram
description: Generate design diagrams from code or a plan - entity-relationship, sequence, flow or state - as Mermaid, and optionally publish a private artifact page. Use when a design needs a picture, for flows with several actors, or when asked for an entity or sequence diagram.
argument-hint: "<er|sequence|flow|state|modules> <subject or path> [--keep] [--show]"
allowed-tools: Read, Grep, Glob, Write, Bash(python3:*), Bash(open:*)
model: sonnet
effort: low
---
1. Read the code or plan for `$ARGUMENTS`; draw only what the code shows. Mark inferred parts with a `%% inferred` comment.
2. Type: `er` for models and relations, `sequence` for request flows with their failure and retry paths, `flow` for control flow, `state` for lifecycles, `modules` for the current module map: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/archdiff.py" --repo <path> [--depth N] --print` (depth 0 is one node per file, for flat packages), then annotate layers and boundaries.
3. Write `.sdlc/design/<subject>.md` (untracked), or `docs/design/<subject>.md` with `--keep`, holding the Mermaid block and a 3-line legend. Under about 15 nodes per diagram; split rather than shrink.
4. A sequence diagram shows the failure path of every external call: timeout, retry, duplicate.
5. Pitfall pass: mark every hazard the code shows where it happens, not in prose elsewhere. In a sequence, label the loop (`loop each account (N+1)`) or add `Note over API: PITFALL ...`; in an ER, annotate the field (`"no index, filtered on"`, `"float money"`, `"nullable, no default"`). Look for: queries in a loop (N+1), filtering, sorting or aggregating in app code, unbounded loads and no pagination, non-deterministic order, several writes without one transaction, check-then-insert instead of a unique constraint, missing index on a filter or order column, read-modify-write on a balance, missing authz on an ID in the path, float money, external call without a deadline, a network call inside a transaction, a lost update, an unindexed foreign key, a locking migration. Each maps to a question in `${CLAUDE_PLUGIN_ROOT}/skills/arch/references/lens.md` or `db.md`.
6. Under the diagram, a `Pitfalls` table: hazard, `file:line`, lens question, fix, and **verified** (read in the code or measured) or **inferred**. Never state an inferred one as fact; say how to confirm it (`assertNumQueries`, `EXPLAIN`).
7. **Timebox running** (brief mode): at most two diagrams, the flow the task changes and the entities it touches; only the three pitfalls that matter for this task, ranked by impact on it; then three lines: what the flow does, the risk handled now and how, the risk deferred and why. No full table.
8. `--show` (or when asked to view it): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" <file>` renders the Mermaid locally and opens it in Chrome; nothing is published.

Reuse the platform when present: if the Artifact tool and the `artifact-diagramming` skill exist and the user asks to view or share, load that skill and publish a private page. Otherwise the markdown file is the deliverable. Never publish unasked.
For a diagram of the current diff, start from `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/archdiff.py"` (writes `docs/arch/<branch>.md`, changed modules highlighted) and refine; with `gates.diagram=require` that file must be in every commit.
