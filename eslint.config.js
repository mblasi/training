// ESLint 9 flat config
// Configuración mínima para el monorepo
import tseslint from 'typescript-eslint';

export default [
  {
    ignores: ['**/node_modules/**', '**/dist/**', '**/.expo/**', '**/build/**'],
  },
  ...tseslint.configs.recommended,
  {
    files: ['**/*.js', '**/*.mjs', '**/*.cjs'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
    },
  },
];
