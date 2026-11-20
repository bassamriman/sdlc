---
name: why
description: Explain the latest diff line by line so the human can defend every change - marks guesses and quizzes the user. Use after any AI-written diff, before accepting it.
argument-hint: "[file or range, default: uncommitted work]"
allowed-tools: Read, Bash(git:*)
model: sonnet
effort: low
---
Diff: `$ARGUMENTS` if given, else `git diff HEAD` plus untracked files (the slice in progress). Hard cap 12 lines.

Read the diff once, in a single call (`git diff --stat` then the diff); never re-run it while explaining.

1. For each hunk: what it does and why that way, one line.
2. Mark every guess or assumption with `GUESS:` and say what would confirm it.
3. Name one alternative you rejected and the trade-off.
4. Ask the user 2 questions about the diff they should answer unaided (what happens on a replayed request, why this status code, why Decimal). Wait for the answers before moving on.

Never defend the design on the user's behalf; surface what they must be able to explain themselves.
Next: `/sdlc:check`, then commit.
