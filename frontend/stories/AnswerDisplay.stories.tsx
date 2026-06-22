import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { AnswerDisplay } from '../components/features/rag/AnswerDisplay'
import { withDarkMode } from './decorators'

const meta: Meta<typeof AnswerDisplay> = {
  title: 'Features/RAG/AnswerDisplay',
  component: AnswerDisplay,
  parameters: {
    nextjs: { appDirectory: true },
    layout: 'padded',
  },
}
export default meta
type Story = StoryObj<typeof AnswerDisplay>

export const Empty: Story = {
  args: { messages: [] },
}

export const Loading: Story = {
  args: {
    messages: [],
    isLoading: true,
  },
}

export const WithAnswer: Story = {
  args: {
    messages: [
      {
        id: '1',
        role: 'assistant',
        content:
          '根據近期研究，以下論文值得關注：\n\n這些論文探討了大型語言模型的優化方向，包含效率與準確性的平衡。\n\n結論是多模型整合能顯著提升整體表現。',
        timestamp: new Date(),
      },
    ],
  },
}

export const WithMarkdownLinks: Story = {
  args: {
    messages: [
      {
        id: '1',
        role: 'assistant',
        content:
          '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法的效果。\n\n2. [Self-RAG](https://arxiv.org/abs/2310.11511) — 自省式檢索增強生成。',
        timestamp: new Date(),
      },
    ],
  },
}

export const LoadingWithExistingAnswer: Story = {
  args: {
    messages: [
      {
        id: '1',
        role: 'assistant',
        content: '根據近期研究，以下論文值得關注：\n\n1. [Self-RAG](https://arxiv.org/abs/2310.11511)',
        timestamp: new Date(),
      },
    ],
    isLoading: true,
  },
}

export const Error429: Story = {
  args: {
    messages: [],
    error: new Error('HTTP 429'),
  },
}

export const Error503: Story = {
  args: {
    messages: [],
    error: new Error('HTTP 503'),
  },
}

export const GenericError: Story = {
  args: {
    messages: [],
    error: new Error('Network error'),
  },
}

export const LoadingDark: Story = {
  name: 'Loading (Dark)',
  args: {
    messages: [],
    isLoading: true,
  },
  decorators: [withDarkMode],
}

export const WithAnswerDark: Story = {
  name: 'WithAnswer (Dark)',
  args: {
    messages: [
      {
        id: '1',
        role: 'assistant',
        content:
          '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法的效果。\n\n2. [Self-RAG](https://arxiv.org/abs/2310.11511) — 自省式檢索增強生成。',
        timestamp: new Date(),
      },
    ],
  },
  decorators: [withDarkMode],
}

export const Error429Dark: Story = {
  name: 'Error 429 (Dark)',
  args: {
    messages: [],
    error: new Error('HTTP 429'),
  },
  decorators: [withDarkMode],
}
