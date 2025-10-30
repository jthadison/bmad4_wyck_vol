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
  ],
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@typescript-eslint/parser',
    ecmaVersion: 'latest',
    sourceType: 'module',
  },
  plugins: ['vue', '@typescript-eslint'],
  rules: {
    // Add any custom rules here
    '@typescript-eslint/no-unused-vars': 'warn',
    'vue/multi-word-component-names': 'off',
  },
  ignorePatterns: ['dist', 'node_modules', '*.config.js', '*.config.ts'],
};
