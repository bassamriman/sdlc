# Coding standard (24 rules)

Tags: H = enforced by the edit hook in every language. HP = by the hook in Python only. L = by the stack's linter when configured (fragments in `stacks/lint/<language>/`, gaps per language in `stacks/lint/README.md`). J = judgement, the reviewer applies it. Short pass (timebox, or a small diff): 1, 3, 4, 7, 10, 14, 16.

1. J Immutable by default: `x.items.append(a)` becomes `x.with_items(x.items + (a,))`.
   Why: a value that cannot change cannot be changed by someone else; most concurrency and aliasing bugs disappear with it.
2. J No shared mutable state; pass and return values.
   Why: state reachable from two places needs locks and discipline; data flowing through function arguments needs neither.
3. J Parse at the boundary, never validate in the middle: `Email.parse(s) -> Result`, downstream code takes `Email`, not `str`.
   Why: validation that returns the same type proves nothing to the next function; a parsed type carries the proof with it.
4. J Make illegal states unrepresentable: `{status, error?, data?}` and flag pairs (`is_loaded and not is_error`) both become `Loading | Failed(err) | Loaded(data)`.
   Why: if the type cannot express "loaded with an error", nobody has to handle it and nobody can produce it by accident.
5. J Sum types for variants, not a `type: str` plus if-chains; a closed type is what lets rule 6 bite.
   Why: a string tag can hold any value; a closed type lets the compiler or linter find every place a new variant must be handled.
6. L Exhaustive matching on closed types: no wildcard that handles a case; where the compiler cannot check, end with a never-typed proof (`case _: assert_never(x)`, `const _: never = x`).
   Why: a wildcard branch is where the new case goes to be silently mishandled; exhaustiveness turns that into a build error.
7. HP/L No boolean flag parameters: `send(msg, True)` becomes `send_now(msg)` / `schedule(msg)` or a `Mode` enum.
   Why: `True` at a call site says nothing; a flag usually means one function doing two jobs.
8. J Solve the problem in front of you: no abstraction with one caller, no config for a value that never varies, no plugin point before a second real use; `PaymentStrategyFactory` with one strategy becomes `charge(payment)`.
   Why: speculative generality is code to read, test and migrate for a need that may never come; the second use will show the right shape.
9. J Total functions: no throwing `head`; return an option.
   Why: a function that can fail on some inputs should say so in its type, not in a stack trace at runtime.
10. J/L Errors as values for expected failures; exceptions only for bugs. Catch only what you handle: never swallow, keep the cause when wrapping (`raise X from e`, `%w`, `cause`), handle or rethrow, never both. HP: bare `except`.
   Why: expected failures (not found, declined, invalid) are part of the contract and must be visible to callers; a swallowed or cause-less error is an unexplainable incident.
11. L No null/None leaking across a function boundary (strict null checks).
   Why: a nullable value crossing a boundary makes every caller guess; the null slips through until it crashes far from its origin.
12. HP/L Methods of 15 lines or fewer, one level of abstraction; extract named steps.
   Why: a method that fits on a screen with one level of detail can be read, named and tested; the names of its steps document it.
13. HP/L At most 3 parameters; group related ones into a value type.
   Why: four loose parameters invite wrong-order bugs and hide the concept they belong to; a value type names it.
14. J Domain types over primitives: `Money(amount, Currency)`, never `float` plus `str`; money is integer minor units or a decimal type, rounded once at a named place with the mode stated, remainders allocated when splitting.
   Why: a float cannot represent 0.10 and a bare number carries no currency; rounding in several places loses cents that reconciliation then finds.
15. J Names carry intent; no `Manager`, `Util`, `Helper`, no abbreviations.
   Why: a name is the cheapest documentation; a vague one means the thing has no single responsibility.
16. H Comments only for a non-obvious WHY (constraint, invariant, external quirk). Never what, never history (`changed X to Y`), no TODO without a ticket id. J: a doc comment on every public contract (inputs, failure values, invariants); none on private code. Doc comments do not count toward density.
   Why: comments that restate code rot the moment the code changes; the only comment that stays true is the reason the code is the way it is.
17. H/L No dead code, no commented-out code (H), no unused imports or parameters (L); git holds history.
   Why: dead code is read, maintained and feared by everyone who does not know it is dead; version control already keeps it.
18. L/J Declarative over imperative (`map/filter/fold`), guard clauses, nesting depth 2 or less.
   Why: a transformation says what the result is; a loop with mutations says how to build it, and the reader must simulate it.
19. J Pure core, effects at the edge; inject clock, randomness and IO. Dependencies point inward: domain code imports no framework, ORM, HTTP or SDK type; adapters map to domain types.
   Why: pure logic is tested without a database or a clock; a domain that depends on a framework cannot outlive it.
20. J Fail fast on invariants in the constructor, not scattered checks. HP: mutable default arguments.
   Why: an object that cannot be constructed invalid never needs defensive checks downstream.
21. H/J No secret literals in source (H: a literal assigned to a name matching key, token, secret, password); no PII, credentials or card data in logs, errors, idempotency keys or URLs; structured log fields, never f-strings; log an error once, at the boundary.
   Why: source and logs are copied, searched and retained far beyond their origin; a secret or a card number there is a breach waiting for a reader.
22. J/L Structured concurrency: every spawned task has an owning scope that awaits it and propagates errors and cancellation; a bare `create_task` / `GlobalScope.launch` or an un-awaited promise is a bug.
   Why: a task nobody awaits fails silently and outlives the request that started it; a scope makes its errors and its lifetime someone's responsibility.
23. J/L Acquire and release in one scope (`with`, try-with-resources, `use`, `defer`, RAII, ZIO `Scope`); never a bare `.close()` on the happy path.
   Why: the release that only runs on the happy path leaks on the first exception, and leaks surface as exhausted pools under load.
24. J/L Time: instants in UTC, zone applied only at the display edge; elapsed time from a monotonic clock; one injected `Clock`; `java.time`, never `Date`.
   Why: a local time without a zone is ambiguous twice a year; wall-clock subtraction goes negative when the clock is adjusted; an injected clock makes time testable.

## By property
- Soundness (the types make wrong states impossible): 3, 4, 5, 6, 9, 11, 14, 20.
- Correctness under change (behaviour stays what it says): 10, 12, 13, 18, 19, 22, 23, 24.
- Integrity (nothing silently lost, leaked or doubled): 1, 2, 10, 14, 21, 23.
- Readability without archeology (the code is the record): 8, 15, 16, 17.

## Python quick form
Prefer `match` with `assert_never` over `if/elif` chains; frozen dataclasses for values; `Ok[T] | Err[E]` as two frozen dataclasses (or `returns.Result`) for expected failures; parse with pydantic or Ninja `Schema` at the API edge; `Decimal` for money, never `float`.
