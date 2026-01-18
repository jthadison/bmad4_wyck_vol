module.exports = {
  root: true,
  env: {
    node: true,
    browser: true,
    es2021: true,
    serviceworker: true, // Enable service worker globals (clients, self, etc.)
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
    // TypeScript rules - downgrade to warnings for gradual adoption
    '@typescript-eslint/no-unused-vars': 'warn',
    '@typescript-eslint/no-explicit-any': 'warn', // Too many violations to fix at once
    // Vue rules
    'vue/multi-word-component-names': 'off',
  },
  ignorePatterns: ['dist', 'node_modules', '*.config.js', '*.config.ts'],
};
