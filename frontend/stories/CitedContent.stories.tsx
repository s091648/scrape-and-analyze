import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { CitedContent } from '../components/features/chat/cited-content'
import type { ArticleSource } from '../components/features/chat/types'

const sources: ArticleSource[] = [
  { id: 'src-1', title: 'Scaling Laws for Multimodal Diffusion Models', url: 'https://arxiv.org/abs/2501.11111', public_article_id: 'article-1' },
  { id: 'src-2', title: 'Constitutional AI: A Survey of Alignment Approaches', url: 'https://arxiv.org/abs/2501.22222', public_article_id: 'article-2' },
  { id: 'src-3', title: null, url: 'https://example.com/no-title-source', public_article_id: null },
]

const text = [
  'This week saw major advances in multimodal AI, with several papers demonstrating new scaling behavior in vision-language models [1].',
  '',
  'Researchers also published a comprehensive survey on constitutional AI approaches for alignment [2], and a widely-discussed blog post summarizing community sentiment [3].',
  '',
  'Key themes:',
  '- Emergent capabilities from combined vision-language pretraining',
  '- Diminishing returns past a certain parameter count [1]',
  '- Open questions about evaluation methodology',
].join('\n')

const meta: Meta<typeof CitedContent> = {
  title: 'Features/Chat/CitedContent',
  component: CitedContent,
  parameters: { layout: 'padded' },
}
export default meta
type Story = StoryObj<typeof CitedContent>

export const WithSourceList: Story = {
  render: (args) => (
    <div className="max-w-xl text-sm text-neutral-700 leading-relaxed">
      <CitedContent {...args} />
    </div>
  ),
  args: {
    text,
    sources,
    showSourceList: true,
  },
}

export const StreamingHidesSourceList: Story = {
  render: (args) => (
    <div className="max-w-xl text-sm text-neutral-700 leading-relaxed">
      <CitedContent {...args} />
    </div>
  ),
  args: {
    text,
    sources,
    showSourceList: false,
  },
}

export const NoSources: Story = {
  render: (args) => (
    <div className="max-w-xl text-sm text-neutral-700 leading-relaxed">
      <CitedContent {...args} />
    </div>
  ),
  args: {
    text: 'A report generated before citations shipped renders as plain text — [1] here is not a link since no sources were supplied.',
  },
}
