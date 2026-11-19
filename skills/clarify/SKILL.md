---
name: clarify
description: Turn a vague requirement into assumptions, edge cases and questions for the requester. Use before planning when requirements are ambiguous or the task involves data modification.
argument-hint: "<requirement text>"
allowed-tools: Read, Grep
model: sonnet
effort: low
---
Do not write code. Do not answer your own questions.

Output, hard cap 8 bullets:
- Restate the requirement in one sentence.
- 3 assumptions you will proceed on unless corrected.
- 3 edge cases (empty input, boundary, duplicate or replay, permission, concurrent write).
- Questions that change the design, most important first, max 3.
- What you will NOT do.

For data modification always cover: validation rule, status codes or error values, idempotency, atomicity (all or nothing), and delete semantics (hard, soft, reversal).
If a diagram exists under `.sdlc/design/`, turn each pitfall that depends on scale or intent into a question ("this loads every row per request; what data size should I design for?").
Next: `/sdlc:plan <feature>`; for a change under about 20 lines, `/sdlc:red <slice>` directly.
