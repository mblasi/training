// ESLint 10 flat config
// Configuración mínima para el monorepo
import tseslint from 'typescript-eslint';
import eslintConfigPrettier from 'eslint-config-prettier';

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
  {
    files: ['**/metro.config.{js,cjs}', '**/babel.config.{js,cjs}'],
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
  eslintConfigPrettier,
];
