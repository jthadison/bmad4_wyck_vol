import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./tests/setup.ts'],
    testTimeout: 15000,
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/tests/smoke/**', // Exclude Playwright smoke tests
      '**/tests/e2e/**', // Exclude Playwright E2E tests
      // Temporarily excluded due to Vitest SCSS worker timeout issues
      // See: https://github.com/vitest-dev/vitest/issues/2834
      '**/tests/components/EquityCurveChart.spec.ts',
      '**/tests/components/BacktestPreview.spec.ts',
      '**/tests/components/RegressionTestDashboard.spec.ts',
      '**/tests/router.test.ts',
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.config.{js,ts}',
        '**/index.ts',
      ],
      thresholds: {
        statements: 90,
        branches: 90,
        functions: 90,
        lines: 90,
      },
    },
  },
})
