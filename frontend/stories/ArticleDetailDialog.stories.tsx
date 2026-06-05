import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { type ComponentProps, useState } from "react";
import { ArticleDetailDialog } from "../components/features/articles/article-detail-dialog";
import { Button } from "../components/ui/button";
import type { ArticleDetail } from "../lib/api/articles";

const meta: Meta<typeof ArticleDetailDialog> = {
  title: "Features/Articles/ArticleDetailDialog",
  component: ArticleDetailDialog,
  parameters: { layout: "centered" },
};

export default meta;
type Story = StoryObj<typeof ArticleDetailDialog>;

const mockDetail: ArticleDetail = {
  id: "1",
  title: "Deep Learning in 2025",
  content:
    "Large language models have demonstrated remarkable capabilities across a wide range of tasks, from natural language understanding to code generation and beyond.",
  source: "arxiv",
  url: "https://arxiv.org/abs/2501.12345",
  published_at: "2025-01-15T10:00:00Z",
  scraped_at: "2025-01-16T08:00:00Z",
  tags: ["Machine Learning", "NLP", "Transformers"],
  model_used: "gemini-2.0-flash",
  pain_points: "Current models struggle with long-context reasoning and factual grounding.",
  insights: "Sparse attention patterns significantly reduce memory overhead without sacrificing accuracy.",
  innovations: "Mixture-of-Experts architecture with dynamic routing achieves 3x throughput improvement.",
  tag_groups: [
    {
      group_name: "domain",
      display_name: "Domain",
      color: "#6366f1",
      tags: ["Machine Learning", "NLP", "Transformers"],
    },
    {
      group_name: "application",
      display_name: "Application",
      color: "#10b981",
      tags: ["Text Generation", "Code Completion"],
    },
  ],
};

function DialogTrigger(
  props: Omit<ComponentProps<typeof ArticleDetailDialog>, "open" | "onOpenChange">
) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Open Dialog</Button>
      <ArticleDetailDialog {...props} open={open} onOpenChange={setOpen} />
    </>
  );
}

export const WithFullAnalysis: Story = {
  render: () => (
    <DialogTrigger
      title="Deep Learning Advances in 2025: A Comprehensive Survey"
      source="arxiv"
      url="https://arxiv.org/abs/2501.12345"
      published_at="2025-01-15T10:00:00Z"
      content="Large language models have demonstrated remarkable capabilities..."
      detail={mockDetail}
      loading={false}
    />
  ),
};

export const ViaOpenAlex: Story = {
  render: () => (
    <DialogTrigger
      title="Scalable Simulation of Digital Twins using OpenAlex"
      source="openalex"
      url="https://doi.org/10.1038/s12345"
      via_source="openalex"
      original_source="Nature Neuroscience"
      published_at="2025-03-10T00:00:00Z"
      content="This paper presents a scalable approach to digital twin simulation..."
      detail={{ ...mockDetail, source: "openalex" }}
      loading={false}
    />
  ),
};

export const ViaSemanticScholar: Story = {
  render: () => (
    <DialogTrigger
      title="Transformer Efficiency via Semantic Scholar Discovery"
      source="semantic_scholar"
      url="https://arxiv.org/abs/2502.99999"
      via_source="semantic_scholar"
      original_source="arxiv"
      published_at="2025-02-20T00:00:00Z"
      content="We propose a novel training curriculum for transformer models..."
      detail={{ ...mockDetail, source: "semantic_scholar" }}
      loading={false}
    />
  ),
};

export const Loading: Story = {
  render: () => (
    <DialogTrigger
      title="Loading Article"
      source="rss"
      url="https://example.com/article"
      published_at={null}
      content=""
      detail={null}
      loading={true}
    />
  ),
};

export const NoAnalysis: Story = {
  render: () => (
    <DialogTrigger
      title="Article Without Analysis Yet"
      source="blog"
      url="https://engineering.example.com/post"
      published_at="2025-03-01T00:00:00Z"
      content="This article has been scraped but not yet analyzed by the LLM pipeline."
      detail={{ ...mockDetail, model_used: null, pain_points: null, insights: null, innovations: null, tag_groups: [] }}
      loading={false}
    />
  ),
};
