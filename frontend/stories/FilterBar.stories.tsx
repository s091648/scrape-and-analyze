import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { FilterBar } from "../components/features/articles/filter-bar";

// FilterBar fetches source/tag options from the API on mount.
// In Storybook those calls will fail silently; the dropdowns will be empty
// but the component renders correctly.

const meta: Meta<typeof FilterBar> = {
  title: "Features/Articles/FilterBar",
  component: FilterBar,
  parameters: { layout: "padded" },
  args: {
    onApply: () => {},
  },
};

export default meta;
type Story = StoryObj<typeof FilterBar>;

export const NoFilters: Story = {
  args: {
    sources: [],
    tags: [],
    publishedAfter: "",
    publishedBefore: "",
    scrapedAfter: "",
    scrapedBefore: "",
    activeFilterCount: 0,
  },
};

export const WithActiveFilters: Story = {
  args: {
    sources: ["arxiv"],
    tags: ["AI", "Robotics"],
    publishedAfter: "2025-01-01",
    publishedBefore: "",
    scrapedAfter: "",
    scrapedBefore: "",
    activeFilterCount: 3,
  },
};
