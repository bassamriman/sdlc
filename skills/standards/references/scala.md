# Scala

- Immutable: case classes, `val`, immutable collections.
- Sum types: `sealed trait` or Scala 3 `enum`; compiler-checked exhaustive `match`.
- Parsed types: opaque types, refined types, smart constructors returning `Either` or `Validated`.
- Flags: `-Wunused:all`, `-Wnonunit-statement`, `-Wvalue-discard`, `-Werror`; `-Wconf` to make non-exhaustive match an error.
- Lint: scalafix `DisableSyntax` (noVars, noNulls, noReturns, noThrows), WartRemover (`Var`, `Null`, `Throw`, `Any`, `DefaultArguments`).
