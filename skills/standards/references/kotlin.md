# Kotlin

- Immutable: `val`, `data class`, `kotlinx.collections.immutable`, read-only `List`.
- Sum types: `sealed interface`/`sealed class`/`enum`; `when` as an expression is exhaustive, no `else` on sealed types.
- Parsed types: `@JvmInline value class` with `init { require(...) }`, or a factory returning `Result`/Arrow `Either`.
- Tools: `allWarningsAsErrors`, detekt (`LongMethod`, `LongParameterList`, `CyclomaticComplexMethod`, `CognitiveComplexMethod` (enable), `UnusedPrivateMember`, `ForbiddenComment`, `GlobalCoroutineUsage`), ktlint.
