// For more info, see https://github.com/storybookjs/eslint-plugin-storybook#configuration-flat-config-format
import storybook from "eslint-plugin-storybook";

import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  prettier,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  ...storybook.configs["flat/recommended"],
  // 025-iac-provisioning US5 / FR-019: every non-test, non-tooling app file must
  // read env vars through lib/env.server.ts or lib/env.client.ts, never
  // process.env directly — see those two files' own header comments.
  {
    rules: {
      "no-restricted-properties": [
        "error",
        {
          object: "process",
          property: "env",
          message:
            "Import from '@/lib/env.server' (server-only) or '@/lib/env.client' (client-safe) instead of reading process.env directly.",
        },
      ],
    },
  },
  {
    files: [
      "lib/env.server.ts",
      "lib/env.client.ts",
      "next.config.ts",
      "playwright.config.ts",
      "scripts/**",
      "tests/**",
      "**/*.test.*",
    ],
    rules: {
      "no-restricted-properties": "off",
    },
  },
]);

export default eslintConfig;
