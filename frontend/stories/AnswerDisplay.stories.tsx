import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { AnswerDisplay } from '../components/features/chat/AnswerDisplay'
import { withDarkMode } from './decorators'

const meta: Meta<typeof AnswerDisplay> = {
  title: 'Features/Chat/AnswerDisplay',
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

export const WithThinking: Story = {
  name: 'WithThinking (collapsed by default)',
  args: {
    messages: [
      {
        id: '1',
        role: 'assistant',
        content: '根據近期研究，RAG 系統能顯著改善大型語言模型的準確率，特別是在知識密集型任務上表現突出。',
        thinking:
          '使用者詢問的是 RAG 系統的效益。讓我逐步思考：\n\n1. RAG 代表 Retrieval-Augmented Generation\n2. 它通過從外部知識庫檢索相關資訊來增強 LLM 的回答\n3. 主要優勢包括：減少幻覺、保持知識最新、無需重新訓練模型\n4. 研究顯示在 QA benchmarks 上有 15-30% 的準確率提升',
        timestamp: new Date(),
      },
    ],
  },
}

export const WithThinkingDark: Story = {
  name: 'WithThinking (Dark)',
  args: {
    messages: [
      {
        id: '1',
        role: 'assistant',
        content: 'RAG 系統能顯著改善大型語言模型的準確率。',
        thinking: '讓我仔細分析這個問題的各個面向，確保回答全面且準確...',
        timestamp: new Date(),
      },
    ],
  },
  decorators: [withDarkMode],
}
