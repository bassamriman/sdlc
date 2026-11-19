# Python (3.12+)

Applies the 24 rules in `rules.md` to Python. Each line is a check; the lint fragment in `stacks/lint/python/pyproject.toml` enforces the ones marked (lint).

## Method splitting
- A function does one thing at one level of abstraction: the top reads as named steps (`order = parse(raw); total = price(order); return render(total)`), the details live in the steps. Limits: 15 statements, 8 branches, 2 nesting levels, complexity 8 (lint `PLR0915`, `PLR0912`, `PLR1702`, `C901`); the edit hook flags functions over 15 lines.
- Extract when a block needs a comment to say what it does: the comment becomes the function name. Extract the loop body, the condition (`if is_overdue(invoice):`), and each branch of a long `if/elif`.
- Separate deciding from doing: a pure function computes the decision (`plan = reconcile(ledger, payments)`), a thin shell performs I/O with it. The pure part is tested without mocks.
- Command or query, not both: a function that returns a value does not mutate its arguments or globals; a function that mutates returns `None`.
- At most 3 positional parameters (lint `PLR0913`); more become a frozen dataclass or keyword-only arguments after `*`. Never a boolean positional flag (lint `FBT001`, `FBT002`): `send(msg, urgent=True)` becomes two functions or an `Enum`.
- Guard clauses and early returns instead of nested `if` (lint `RET`, `SIM`); no `else` after `return`.
- No unused parameters (lint `ARG`); no dead or commented-out code (lint `ERA001`).

## Immutability
- Values are `@dataclass(frozen=True, slots=True, kw_only=True)`; change with `dataclasses.replace(order, status=Status.PAID)` or a `with_*` method returning a new instance.
- Collections in values and signatures: `tuple`, `frozenset`, `Mapping`/`Sequence` (read-only views) instead of `list`/`dict`/`set`; build with comprehensions, not append loops.
- Constants are `Final` and module level; class-level mutable defaults are `ClassVar` or gone (lint `RUF012`).
- No mutable default arguments (lint `B006`); `field(default_factory=tuple)` in dataclasses.
- No module-level mutable state and no `global` (lint `PLW0603`); pass state in, return state out. Caches only on pure functions (`functools.cache`), never on methods holding `self`.
- Pydantic models at the boundary use `model_config = ConfigDict(frozen=True, strict=True, extra="forbid")`.
- Do not mutate arguments: a function that receives a `list` returns a new one.

## Pattern matching and sum types
- A closed set of cases is a sum type: a union of frozen dataclasses (`type Payment = Card | Bank | Wallet`), an `Enum`/`StrEnum`, or a `Literal`. Not a string compared in `if` chains, not a pair of booleans.
- Branch on it with `match`, one `case` per variant with class patterns that bind fields (`case Card(last4=last4):`), and end with `case _: assert_never(x)` so a new variant is a type error (mypy `exhaustive-match`).
- No `isinstance` chains or `type(x) ==` over a closed set; no `case _:` that silently returns a default.
- Guards (`case Bank(amount=a) if a > LIMIT:`) for conditions on fields; keep each case body a call to a named function when it exceeds a few lines.
- Match on structure for parsed input (`case {"type": "refund", "id": str(id_)}:`) only after the boundary has parsed it; inside the core, match on types.
- Errors as values where failure is expected (rule 10): `Ok[T] | Err[E]` as two frozen dataclasses (or `returns.Result`), matched exhaustively; exceptions stay for bugs and infrastructure failures.

## Comments and docstrings
- Docstring on every public module, class and function: what it does and its contract (inputs, return, raised errors or `Err` values, invariants), first line a one-sentence summary; none on private helpers whose name says it.
- Inline comments only for a non-obvious constraint, stated positively: `# the provider rejects batches over 100`, not `# couldn't send all at once because the API failed`.
- No history (`# previously`, `# changed to`, `# no longer`, `# now uses`, dates, ticket trails), no narration of the next line, no section banners, no commented-out code (lint `ERA001`; the edit hook also flags history, negative and tentative wording and comment density).
- `# TODO` only with a ticket id (lint `TD003`); `# noqa`/`# type: ignore` only with the rule code.

## Types
- Checked strict: mypy `strict` with `warn_unreachable` (or pyright strict; `ty` once it covers exhaustiveness). Every public function annotated (lint `ANN`).
- Modern syntax: `X | None`, `list[int]`, PEP 695 generics (`def first[T](xs: Sequence[T]) -> T`, `type Pair[T] = tuple[T, T]`), `Self`, `@override` on overriding methods, `TypeIs` (3.13) for narrowing predicates (lint `UP`).
- No `Any` in signatures, no `cast` without a comment saying why it holds, `# type: ignore[code]` only with the code and a reason.
- Parsed types for domain values: `NewType` or a frozen dataclass with a `parse` classmethod returning `Result`; `Annotated[int, Field(gt=0)]` at pydantic boundaries.
- `Protocol` for dependencies the code calls (structural, easy to fake in tests); ABCs only for shared implementation.
- `TypedDict` (with `Required`/`NotRequired`/`ReadOnly`) only for JSON shapes you do not own; inside the core, dataclasses.

## Errors and resources
- Raise specific exceptions; never bare `except:` or `except Exception` that continues (lint `E722`, `BLE001`, `S110`); re-raise with `raise DomainError(...) from e` (lint `B904`); add context with `e.add_note(...)`.
- `try` blocks wrap the one call that can fail, not the function (lint `TRY`); no exceptions for control flow.
- Every file, lock, connection and temp dir in a `with` (lint `SIM115`); `contextlib.ExitStack` for a variable number; `pathlib.Path` over `os.path` (lint `PTH`); explicit `encoding="utf-8"` on text I/O (lint `PLW1514`).

## Time, money, numbers
- Aware datetimes only: `datetime.now(UTC)`, `zoneinfo.ZoneInfo` for local display (lint `DTZ`); store UTC.
- Durations and timeouts with `time.monotonic()`, never wall clock.
- Money as `Decimal` from strings or integer minor units, never `float`; rounding mode stated (`ROUND_HALF_EVEN` or what the business says).
- Inject the clock and randomness (`now: Callable[[], datetime]`) into code that depends on them.

## Async and concurrency
- Structured concurrency: `async with asyncio.TaskGroup()`, deadlines with `async with asyncio.timeout(s)`; a bare `create_task` keeps a reference (lint `RUF006`).
- No blocking calls in `async def` (lint `ASYNC`): use the async client or `asyncio.to_thread`.
- Never swallow `CancelledError`; handle `ExceptionGroup` from task groups with `except*`.
- Threads for blocking I/O, processes for CPU-bound work; shared state only behind a queue or lock, preferably not at all.

## Security
- `subprocess.run([...], check=True, timeout=...)`, never `shell=True` with interpolated input (lint `S602`, `S603`).
- No `eval`, `exec`, `pickle` or `yaml.load` on untrusted data (`yaml.safe_load`, `json`); `defusedxml` for XML (lint `S`).
- `secrets` for tokens, never `random` (lint `S311`); parameterized SQL only, never f-strings into queries (lint `S608`); no secrets in code (the edit hook flags literals).

## Logging and output
- `logger = logging.getLogger(__name__)` per module; lazy arguments `logger.info("paid %s", order_id)`, never f-strings in log calls (lint `G004`); `logger.exception` inside `except`.
- No `print` in library code (lint `T20`); structured fields (`extra=`) for anything a dashboard will query.

## Structure and performance
- No side effects at import time; entry points under `if __name__ == "__main__":`; no star imports; `__all__` on public modules.
- Comprehensions and generators over manual loops (lint `PERF`, `C4`); `set`/`dict` lookups instead of `in list` inside loops; `itertools.batched` for chunking.
- Profile before optimizing; `__slots__` via `slots=True` on hot value types.

## Tests
- pytest; one behaviour per test, named for it; `pytest.mark.parametrize` for tables; `pytest.raises(Error, match=...)`.
- Fakes over mocks: a `Protocol` plus an in-memory implementation; mock only at process boundaries (HTTP, clock, queue).
- Property tests (`hypothesis`) for parsers, serializers and anything with an inverse.
- No network, sleep or wall clock in unit tests.

## Django / Ninja / FastAPI
- Parse request bodies into Ninja `Schema` or pydantic models at the edge; keep rules in pure functions, not models, views or serializers.
- `select_related`/`prefetch_related` against N+1 (prove with `assertNumQueries`); aggregate in SQL (`Sum`, `Case/When`, `F()`), not Python loops; deterministic ordering (`order_by("created_at", "id")`).
- `transaction.atomic` around multi-row writes; `select_for_update` or `F()` updates against lost updates; side effects after commit with `transaction.on_commit`.
- `get_or_create`/`update_or_create` backed by a unique constraint; `bulk_create`/`bulk_update` for batches.
- Migrations reversible; data migrations separate from schema migrations (see `arch/references/db.md`).
- `Decimal` fields for money; `Err` mapped to a status code in one place, never in a model or service.
