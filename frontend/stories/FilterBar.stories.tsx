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
    aggregators: [],
    originalSources: [],
    tags: [],
    tagGroups: [],
    publishedAfter: "",
    publishedBefore: "",
    scrapedAfter: "",
    scrapedBefore: "",
    activeFilterCount: 0,
  },
};

export default meta;
type Story = StoryObj<typeof FilterBar>;

export const NoFilters: Story = {};

export const WithSourceFilter: Story = {
  args: {
    originalSources: ["arxiv"],
    tags: ["AI", "Robotics"],
    publishedAfter: "2025-01-01",
    activeFilterCount: 3,
  },
};

export const WithAggregatorFilter: Story = {
  args: {
    aggregators: ["openalex", "semantic_scholar"],
    activeFilterCount: 2,
  },
};

export const WithAllFilters: Story = {
  args: {
    aggregators: ["openalex"],
    originalSources: ["arxiv"],
    tags: ["Machine Learning"],
    tagGroups: ["domain"],
    publishedAfter: "2025-01-01",
    publishedBefore: "2026-01-01",
    activeFilterCount: 5,
  },
};
