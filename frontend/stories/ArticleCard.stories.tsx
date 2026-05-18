import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { ArticleCard } from '../components/features/articles/article-card'

const meta: Meta<typeof ArticleCard> = {
  title: 'Features/Articles/ArticleCard',
  component: ArticleCard,
  args: {
    id: 'article-uuid-1',
    title: 'Understanding Transformer Architecture in Modern LLMs',
    source: 'arxiv',
    content:
      'This paper introduces a novel approach to scaling transformer models by leveraging mixture-of-experts architecture. We demonstrate that our method achieves state-of-the-art performance on multiple benchmarks while reducing computational costs by 40%. Experiments on GPT-4-scale models confirm that routing efficiency is the primary bottleneck in sparse MoE systems.',
    url: 'https://arxiv.org/abs/2405.00001',
    published_at: '2026-05-01T00:00:00Z',
    scraped_at: '2026-05-02T12:00:00Z',
  },
}
export default meta
type Story = StoryObj<typeof ArticleCard>

export const Default: Story = {}

export const NoPublishedDate: Story = {
  args: {
    published_at: null,
    scraped_at: null,
  },
}

export const LongTitle: Story = {
  args: {
    title:
      'A Comprehensive Survey of Large Language Model Alignment Techniques: From RLHF to Constitutional AI and Direct Preference Optimization',
  },
}

export const BlogSource: Story = {
  args: {
    source: 'engineering.atspotify.com',
    title: 'How We Reduced ML Inference Latency by 60%',
    content:
      'Over the past year, our ML platform team has been working on reducing the inference latency of our recommendation models. Through a combination of model distillation, quantization, and batching optimizations, we achieved a 60% reduction in p99 latency.',
    url: 'https://engineering.atspotify.com/2026/05/ml-inference-latency',
    scraped_at: '2026-05-10T08:00:00Z',
  },
}
