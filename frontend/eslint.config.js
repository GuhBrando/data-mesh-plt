import js from '@eslint/js'
import globals from 'globals'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import security from 'eslint-plugin-security'
import tanstackQuery from '@tanstack/eslint-plugin-query'

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'coverage', '.stryker-tmp'] },
  {
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      ...tanstackQuery.configs['flat/recommended'],
    ],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'security': security,
    },
    rules: {
      ...reactHooks.configs['recommended-latest'].rules,
      ...security.configs.recommended.rules,
      'complexity': ['error', 15],
      // TypeScript's type system makes this rule a false positive for typed Record access
      'security/detect-object-injection': 'off',
      // The three rules below ship with the React Compiler ruleset added in
      // eslint-plugin-react-hooks v6/v7. That major bump was required to reach an
      // eslint 10 that resolves the brace-expansion DoS advisory (GHSA-mh99-v99m-4gvg);
      // it was not an opt-in to a new ruleset. Each flags pre-existing code that the
      // previous plugin (v5, which shipped only rules-of-hooks and exhaustive-deps)
      // never analysed, and `react-hooks/refs` in particular misfires on
      // react-hook-form's `handleSubmit`, which is a stable callback rather than a ref.
      // Deferred so the CVE fix stays surgical; the remaining 11 new rules are active
      // and passing. Re-enable and address the findings in a dedicated change.
      'react-hooks/refs': 'off',
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/incompatible-library': 'off',
    },
  },
)
