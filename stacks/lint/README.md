# Lint fragments per language

Drop-in configs that make the stack's own linter enforce the coding standard (rules.md tag `L`). `init` offers the matching fragment when the repo has no linter config; it never applies one unasked, and never in a repo you do not own. Rule names were verified against each tool's docs on 2026-11-13; lines marked UNVERIFIED were not.

| Language | Files | Check-only command | The reviewer must still own |
|---|---|---|---|
| Python | `python/pyproject.toml` | `ruff check --no-fix .` and `mypy .` | forbidding a `case _:` that handles a case (`case _: assert_never(x)` is required); `frozen=True`; TD003 wants an issue link, not an id |
| TypeScript | `typescript/eslint.config.mjs`, `tsconfig.json` | `npx eslint . --max-warnings 0`, `npx tsc --noEmit` | boolean parameters; commented-out code; TODO-with-ticket (`no-warning-comments` bans all TODOs) |
| Scala 3 | `scala/build.sbt`, `.scalafix.conf` | `sbt "scalafixAll --check"`, `sbt compile` | method length, parameter count, complexity, nesting (no tool); boolean params; `case _` on sealed types; empty catch |
| Java 21 | `java/checkstyle.xml`, `pmd-ruleset.xml`, `errorprone.flags` | `checkstyle -c checkstyle.xml src`, `pmd check -d src -R pmd-ruleset.xml` | boolean parameters; commented-out code; mutable statics |
| Kotlin | `kotlin/detekt.yml`, `.editorconfig` | `detekt --config detekt.yml --build-upon-default-config --input src`, `ktlint 'src/**/*.kt'` | boolean parameters; commented-out code; immutability beyond var-to-val |
| Go | `go/.golangci.yml` | `golangci-lint run ./...` | immutability (no readonly aggregates); forbidding `default:` on enum switches |
| Rust | `rust/Cargo.toml`, `clippy.toml` | `cargo clippy --all-targets --no-deps -- -D warnings` | commented-out code; TODO comments; overuse of `mut` |

Cross-language: only Python (`FBT001`), Go (`flag-parameter`) and Rust (`max-fn-params-bools = 0`) catch boolean parameters mechanically; only Python (`ERA001`) and Go (`commentedOutCode`) catch commented-out code. The edit hook covers comment rules in every language and the size rules in Python; everything else in that last column is for `/sdlc:standards`.
