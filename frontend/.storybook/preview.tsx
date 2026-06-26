import type { Preview } from "@storybook/nextjs-vite";
import React from "react";
import { Toaster } from "sonner";
import { I18nProvider } from "../lib/providers/i18n-provider";
import { ThemeProvider } from "../lib/providers/theme-provider";
import "../app/globals.css";
import "./chatbot-ui/base.css";

const preview: Preview = {
  decorators: [
    (Story) => (
      <ThemeProvider>
        <I18nProvider>
          <Story />
          <Toaster richColors position="bottom-right" />
        </I18nProvider>
      </ThemeProvider>
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
