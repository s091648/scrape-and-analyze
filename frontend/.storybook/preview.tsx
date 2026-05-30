import type { Preview } from "@storybook/nextjs-vite";
import React from "react";
import { Toaster } from "sonner";
import { I18nProvider } from "../lib/providers/i18n-provider";
import "../app/globals.css";

const preview: Preview = {
  decorators: [
    (Story) => (
      <I18nProvider>
        <Story />
        <Toaster richColors position="bottom-right" />
      </I18nProvider>
    ),
  ],
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      test: "todo",
    },
  },
};

export default preview;
