# Rust

- Immutable by default; avoid `mut` outside local scope.
- Sum types: `enum` with data; `match` is exhaustive, avoid `_ =>` on owned enums (`#[non_exhaustive]` only for public API evolution).
- Parsed types: newtype with a private field plus `TryFrom`/`FromStr`; `Result` with `?`; `thiserror`.
- Clippy: `wildcard_enum_match_arm`, `match_wildcard_for_single_variants`, `unwrap_used`, `expect_used`, `panic`, `too_many_lines`, `too_many_arguments`, `cognitive_complexity`, `fn_params_excessive_bools`, `struct_excessive_bools`; `-D warnings`; `#![forbid(unsafe_code)]`.
- Value types derive `Debug, Clone, PartialEq, Eq` (`Hash`/`Ord` where meaningful); `#[must_use]` on pure fns and builders (clippy `must_use_candidate`).
