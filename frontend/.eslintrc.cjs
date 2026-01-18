// Technical debt tracking: https://github.com/jthadison/bmad4_wyck_vol/issues/191
module.exports = {
  root: true,
  env: {
    node: true,
    browser: true,
    es2021: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier',
  ],
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@typescript-eslint/parser',
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  plugins: ['vue', '@typescript-eslint'],
  globals: {
    NodeJS: 'readonly', // Node.js types used in Vue components (setTimeout, setInterval types)
  },
  rules: {
    // TypeScript rules
    '@typescript-eslint/no-unused-vars': 'warn',
    '@typescript-eslint/no-explicit-any': 'error', // Restored to error - all violations fixed (issue #191)
    // Vue rules
    'vue/multi-word-component-names': 'off',
  },
  overrides: [
    {
      // Service worker files need serviceworker globals (clients, self, etc.)
      files: ['public/sw.js', '**/sw.js'],
      env: {
        serviceworker: true,
      },
    },
  ],
  ignorePatterns: ['dist', 'node_modules', '*.config.js', '*.config.ts'],
};
