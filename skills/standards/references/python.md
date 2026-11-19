# Python

- Immutable: `@dataclass(frozen=True, slots=True)`, pydantic `ConfigDict(frozen=True)`, `tuple`, `frozenset`, `Mapping`.
- Sum types: union of frozen dataclasses or `Enum`/`Literal`. Match with `match`, end with `case _: assert_never(x)`.
- Parsed types: `NewType`, pydantic `BaseModel`/`TypeAdapter`, `Annotated[..., Field(...)]`; constructor validation in `__post_init__`.
- Checker: `ty` or mypy strict (`warn_unreachable`, `disallow_any_explicit`).
- Ruff rules: `ANN`, `B` (B006 mutable default, B904 cause), `FBT` (boolean traps), `C901`, `PLR0913`, `PLR0915`, `ERA` (commented-out code), `RET`, `SIM` (SIM115 unclosed file), `TRY`, `UP`, `F401`, `F841`, `DTZ` (naive datetime), `RUF006` (un-awaited task), `G`/`LOG` (log formatting).
- Django/Ninja: parse request bodies into Ninja `Schema` at the edge; keep rules in pure functions, not models or views; `select_related`/`prefetch_related` against N+1; `transaction.atomic` around multi-row writes; `get_or_create` backed by a unique constraint; `Decimal` for money; DB aggregates (`Sum` with `Case/When`) instead of Python loops; deterministic ordering (`date`, `id`).
- Errors as values (rule 10): `Ok[T] | Err[E]` as two frozen dataclasses (or `returns.Result`), matched exhaustively; Django/Ninja maps `Err` to a status code in one place, never in a model or service.
