import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { SearchBar } from "../components/features/articles/search-bar";

const meta: Meta<typeof SearchBar> = {
  title: "Features/Articles/SearchBar",
  component: SearchBar,
  parameters: { layout: "padded" },
  args: {
    value: "",
    onSubmit: () => {},
    onClear: () => {},
  },
};

export default meta;
type Story = StoryObj<typeof SearchBar>;

export const Empty: Story = {};

export const WithQueryTyped: Story = {
  args: {
    value: "machine learning",
  },
};
