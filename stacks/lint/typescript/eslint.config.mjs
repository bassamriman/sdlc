// Check: npx eslint . --max-warnings 0 (no --fix). Needs typescript-eslint and eslint-plugin-functional.
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";
import functional from "eslint-plugin-functional";

export default defineConfig(
  tseslint.configs.strictTypeChecked,
  functional.configs.externalTypeScriptRecommended,
  functional.configs.recommended,
  {
    languageOptions: { parserOptions: { projectService: true } },
    rules: {
      "max-lines-per-function": ["error", 15],
      "max-params": ["error", 3],
      "complexity": ["error", 8],
      "max-depth": ["error", 2],
      "no-empty": "error",
      "no-warning-comments": "error",
      "@typescript-eslint/no-unused-vars": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/prefer-readonly": "error",
      "@typescript-eslint/switch-exhaustiveness-check": ["error",
        { allowDefaultCaseForExhaustiveSwitch: false, considerDefaultExhaustiveForUnions: false }],
      "functional/no-let": "error",
      "functional/immutable-data": "error",
      "functional/prefer-immutable-types": "error",
    },
  },
);
