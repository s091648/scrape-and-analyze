import type { StorybookConfig } from '@storybook/nextjs-vite';
import path from 'path';
import { fileURLToPath } from 'url';

const dirname =
  typeof __dirname !== 'undefined'
    ? __dirname
    : path.dirname(fileURLToPath(import.meta.url));

const config: StorybookConfig = {
  stories: [
    '../stories/**/*.mdx',
    '../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)',
  ],
  addons: [
    '@chromatic-com/storybook',
    '@storybook/addon-a11y',
    '@storybook/addon-docs',
    '@storybook/addon-mcp',
    'storybook-addon-module-mock',
  ],
  framework: '@storybook/nextjs-vite',
  staticDirs: ['../public'],
  viteFinal: async (config) => {
    const { storybookTest } = await import('@storybook/addon-vitest/vitest-plugin');
    config.plugins ??= [];
    config.plugins.push(storybookTest({ configDir: dirname }));
    return config;
  },
};

export default config;
