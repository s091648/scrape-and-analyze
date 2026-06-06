import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import {
  SourceCard,
  GlowDot,
  ActivityGraph,
  ActiveBadge,
  type ScraperSetting,
} from "../components/features/scraper/scraper-source-card";

const meta: Meta = {
  title: "Features/Scraper/SourceCard",
  parameters: { layout: "padded" },
};

export default meta;
type Story = StoryObj;

const noop = async () => {};

const baseSetting: ScraperSetting = {
  id: "1",
  source_type: "rss",
  name: "Hacker News",
  url: "https://news.ycombinator.com/rss",
  frequency: 24,
  is_active: true,
  last_scraped_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
  activity: [0, 2, 5, 3, 0, 1, 8, 4, 6, 2, 0, 3, 7, 5],
};

export const RssSource: Story = {
  render: () => (
    <div className="max-w-md">
      <SourceCard
        setting={baseSetting}
        onUpdate={noop}
        onDelete={noop}
        rssKeywords={[
          { id: "k1", keyword: "AI" },
          { id: "k2", keyword: "machine learning" },
        ]}
        onAddRssKeyword={noop}
        onDeleteRssKeyword={noop}
      />
    </div>
  ),
};

export const BlogSource: Story = {
  render: () => (
    <div className="max-w-md">
      <SourceCard
        setting={{
          ...baseSetting,
          id: "2",
          source_type: "blog",
          name: "The Batch (DeepLearning.AI)",
          url: "https://www.deeplearning.ai/the-batch",
          frequency: 168,
          selector_config: { article_link: "a.post-link", title: "h2.title", content: ".post-body" },
        }}
        onUpdate={noop}
        onDelete={noop}
      />
    </div>
  ),
};

export const SemanticScholarSource: Story = {
  render: () => (
    <div className="max-w-md">
      <SourceCard
        setting={{
          ...baseSetting,
          id: "3",
          source_type: "semantic_scholar",
          name: "Semantic Scholar",
          url: "",
          frequency: 24,
          selector_config: { type: "semantic_scholar", max_results: 20, days_back: 7 },
        }}
        onUpdate={noop}
        onDelete={noop}
      />
    </div>
  ),
};

export const OpenAlexSource: Story = {
  render: () => (
    <div className="max-w-md">
      <SourceCard
        setting={{
          ...baseSetting,
          id: "4",
          source_type: "openalex",
          name: "OpenAlex",
          url: "",
          frequency: 24,
          selector_config: { type: "openalex", max_results: 20, days_back: 7 },
        }}
        onUpdate={noop}
        onDelete={noop}
      />
    </div>
  ),
};

export const InactiveSource: Story = {
  render: () => (
    <div className="max-w-md">
      <SourceCard
        setting={{ ...baseSetting, is_active: false, activity: Array(14).fill(0) }}
        onUpdate={noop}
        onDelete={noop}
      />
    </div>
  ),
};

export const NoActivityData: Story = {
  render: () => (
    <div className="max-w-md">
      <SourceCard
        setting={{ ...baseSetting, activity: undefined, last_scraped_at: null }}
        onUpdate={noop}
        onDelete={noop}
      />
    </div>
  ),
};

// ── Sub-components ────────────────────────────────────────────────────────────

export const GlowDotActive: StoryObj = {
  render: () => (
    <div className="flex gap-4 items-center p-4">
      <GlowDot active={true} />
      <span className="text-sm">Active</span>
      <GlowDot active={false} />
      <span className="text-sm">Inactive</span>
    </div>
  ),
};

export const ActivityGraphVariants: StoryObj = {
  render: () => (
    <div className="space-y-4 p-4">
      <ActivityGraph activity={[0, 2, 5, 3, 0, 1, 8, 4, 6, 2, 0, 3, 7, 5]} />
      <ActivityGraph activity={Array(14).fill(0)} />
      <ActivityGraph activity={[10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]} />
    </div>
  ),
};

export const ActiveBadgeVariants: StoryObj = {
  render: () => (
    <div className="flex gap-4 p-4">
      <ActiveBadge active={true} onToggle={() => {}} />
      <ActiveBadge active={false} onToggle={() => {}} />
    </div>
  ),
};
