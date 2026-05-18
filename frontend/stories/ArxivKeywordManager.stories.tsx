import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { ArxivKeywordManager } from "../components/features/scraper/arxiv-keyword-manager";

const noop = async () => {};

const meta: Meta<typeof ArxivKeywordManager> = {
  title: "Features/Scraper/ArxivKeywordManager",
  component: ArxivKeywordManager,
  parameters: { layout: "padded" },
  args: {
    onAddKeyword: noop,
    onDeleteKeyword: noop,
    onAddCategory: noop,
    onDeleteCategory: noop,
  },
};

export default meta;
type Story = StoryObj<typeof ArxivKeywordManager>;

export const Empty: Story = {
  render: (args) => (
    <div className="max-w-xl border border-border rounded-xl p-5">
      <ArxivKeywordManager {...args} />
    </div>
  ),
  args: {
    keywords: [],
    categories: [],
  },
};

export const WithKeywordsAndCategories: Story = {
  render: (args) => (
    <div className="max-w-xl border border-border rounded-xl p-5">
      <ArxivKeywordManager {...args} />
    </div>
  ),
  args: {
    keywords: [
      { id: "k1", keyword: 'ti:"digital twin"' },
      { id: "k2", keyword: "abs:cyber-physical" },
      { id: "k3", keyword: 'ti:"large language model"' },
    ],
    categories: [
      { id: "c1", keyword: "cs.AI" },
      { id: "c2", keyword: "cs.LG" },
      { id: "c3", keyword: "cs.RO" },
    ],
  },
};
