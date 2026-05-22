import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin';
import { playwright } from '@vitest/browser-playwright';

const dirname = typeof __dirname !== 'undefined' ? __dirname : path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    storybookTest({
      configDir: path.join(dirname, '.storybook')
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.')
    }
  },
  test: {
    name: 'storybook',
    browser: {
      enabled: true,
      headless: true,
      provider: playwright({}),
      instances: [{
        browser: 'chromium'
      }]
    }
  }
});
