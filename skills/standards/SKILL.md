---
name: standards
description: Review a diff or file against the coding standard - immutability, parse-don't-validate, ADTs with pattern matching, no flag booleans, concise methods, comment discipline. Use after a slice, before commit, or on any file the user names.
argument-hint: "[file or range, default: working tree vs the recorded base]"
allowed-tools: Read, Grep, Glob, Bash(git:*)
model: sonnet
effort: low
---
Load `${CLAUDE_PLUGIN_ROOT}/skills/standards/references/rules.md` and `${CLAUDE_PLUGIN_ROOT}/skills/standards/references/<language>.md` for each language in `.sdlc/stack.json`.

Procedure:
1. Diff: `$ARGUMENTS` if given, else `git diff <base_sha from .sdlc/state.json>` (includes uncommitted work), else `git diff HEAD`.
2. Already checked by the edit hook in every language: history comments, TODO without ticket, commented-out code, comment density. In Python only: method length, parameter count, bool parameters, mutable defaults, bare except. For other languages those five are checked only if the repo's linter config enforces them (see the language file); otherwise check them here.
3. Spend the rest on judgement rules: missing domain types, stringly-typed variants that want a sum type, validation that should be a parse step, expected failures thrown, swallowed or re-raised without cause, mutation that could be a value transform, PII or secrets in log lines, fire-and-forget tasks, resources without a scope, speculative abstraction (rule 8), comments that restate code.
4. Report only at confidence 80 or higher.

Output, hard cap 10 lines, each `file:line rule# - problem - fix in one clause`, ending with the single change that most improves the diff. This verb never edits.
Next: `/sdlc:check` then commit, or `/sdlc:wrap`.
When a rule is broken at one site, Grep the repo for the same construct and report every site; the fix covers all of them or waits.
