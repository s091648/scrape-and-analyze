import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    exclude: ['**/node_modules/**', '**/tests/integration/**'],
    env: {
      NEXTAUTH_SECRET: 'test-secret',
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['components/**', 'hooks/**', 'lib/**'],
      exclude: [
        'components/ui/**',
        '**/*.d.ts',
        'tests/integration/**',
      ],
    },
  },
})