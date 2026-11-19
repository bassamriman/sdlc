# TypeScript

- Immutable: `readonly`, `ReadonlyArray`, `as const`, `Readonly<T>`.
- Sum types: discriminated unions (`{kind:"A"} | {kind:"B"}`); exhaustive `switch` ending in `const _: never = x`.
- Parsed types: Zod or valibot at the boundary (`z.infer`), branded types (`string & {__brand: "Email"}`).
- tsconfig: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`.
- typescript-eslint: `switch-exhaustiveness-check`, `no-unnecessary-condition`, `no-floating-promises`, `prefer-readonly`, `no-explicit-any`, `no-non-null-assertion`; `eslint-plugin-functional` (`immutable-data`, `no-let`); `max-lines-per-function`, `complexity`.
- React: derive state instead of storing it; model async state as a union (`idle | loading | error | success`), not three booleans.
