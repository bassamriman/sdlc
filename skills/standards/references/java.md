# Java

- Immutable: `record`, `List.of`, `Collections.unmodifiable*`, `final`.
- Sum types: `sealed interface ... permits` plus records; exhaustive `switch` expressions with pattern matching (Java 21), no `default` on sealed types.
- Parsed types: records with compact-constructor validation; `Optional` for return values only.
- Tools: Error Prone (`MissingCasesInEnumSwitch`, `ReturnValueIgnored`), NullAway, `-Xlint:all -Werror`, Checkstyle (`MethodLength`, `ParameterNumber`, `BooleanExpressionComplexity`), SpotBugs, PMD.
- Nullness (rule 11, L): JSpecify `@NullMarked` in every `package-info.java`; NullAway with `-XepOpt:NullAway:JSpecifyMode=true`; unmarked packages are unchecked.
