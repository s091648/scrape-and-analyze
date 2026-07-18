import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { AnswerDisplay } from '../components/features/chat/AnswerDisplay'
import { withDarkMode } from './decorators'
import type { ConversationTurn } from '../components/features/chat/types'

const meta: Meta<typeof AnswerDisplay> = {
  title: 'Features/Chat/AnswerDisplay',
  component: AnswerDisplay,
  parameters: {
    nextjs: { appDirectory: true },
    layout: 'padded',
  },
  args: {
    onPrevTurn: () => {},
    onNextTurn: () => {},
  },
}
export default meta
type Story = StoryObj<typeof AnswerDisplay>

function makeTurn(content: string, opts: { thinking?: string; userContent?: string } = {}): ConversationTurn {
  return {
    userMessage: opts.userContent
      ? { id: 'u1', role: 'user', content: opts.userContent, timestamp: new Date() }
      : undefined,
    assistantMessage: { id: 'a1', role: 'assistant', content, thinking: opts.thinking, timestamp: new Date() },
    sources: [],
  }
}

export const Empty: Story = {
  args: { turns: [], currentIndex: 0 },
}

export const Loading: Story = {
  args: {
    turns: [],
    currentIndex: 0,
    isLoading: true,
  },
}

export const WithAnswer: Story = {
  args: {
    turns: [makeTurn(
      '根據近期研究，以下論文值得關注：\n\n這些論文探討了大型語言模型的優化方向，包含效率與準確性的平衡。\n\n結論是多模型整合能顯著提升整體表現。',
      { userContent: '最近有哪些值得關注的研究？' }
    )],
    currentIndex: 0,
  },
}

export const WithMarkdownLinks: Story = {
  args: {
    turns: [makeTurn(
      '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法的效果。\n\n2. [Self-RAG](https://arxiv.org/abs/2310.11511) — 自省式檢索增強生成。'
    )],
    currentIndex: 0,
  },
}

export const LoadingWithExistingAnswer: Story = {
  args: {
    turns: [makeTurn('根據近期研究，以下論文值得關注：\n\n1. [Self-RAG](https://arxiv.org/abs/2310.11511)')],
    currentIndex: 0,
    isLoading: true,
  },
}

export const Error429: Story = {
  args: {
    turns: [],
    currentIndex: 0,
    error: new Error('HTTP 429'),
  },
}

export const Error503: Story = {
  args: {
    turns: [],
    currentIndex: 0,
    error: new Error('HTTP 503'),
  },
}

export const GenericError: Story = {
  args: {
    turns: [],
    currentIndex: 0,
    error: new Error('Network error'),
  },
}

export const LoadingDark: Story = {
  name: 'Loading (Dark)',
  args: {
    turns: [],
    currentIndex: 0,
    isLoading: true,
  },
  decorators: [withDarkMode],
}

export const WithAnswerDark: Story = {
  name: 'WithAnswer (Dark)',
  args: {
    turns: [makeTurn(
      '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法的效果。\n\n2. [Self-RAG](https://arxiv.org/abs/2310.11511) — 自省式檢索增強生成。'
    )],
    currentIndex: 0,
  },
  decorators: [withDarkMode],
}

export const Error429Dark: Story = {
  name: 'Error 429 (Dark)',
  args: {
    turns: [],
    currentIndex: 0,
    error: new Error('HTTP 429'),
  },
  decorators: [withDarkMode],
}

export const WithThinking: Story = {
  name: 'WithThinking (collapsed by default)',
  args: {
    turns: [makeTurn(
      '根據近期研究，RAG 系統能顯著改善大型語言模型的準確率，特別是在知識密集型任務上表現突出。',
      { thinking: '使用者詢問的是 RAG 系統的效益。讓我逐步思考：\n\n1. RAG 代表 Retrieval-Augmented Generation\n2. 它通過從外部知識庫檢索相關資訊來增強 LLM 的回答\n3. 主要優勢包括：減少幻覺、保持知識最新、無需重新訓練模型\n4. 研究顯示在 QA benchmarks 上有 15-30% 的準確率提升' }
    )],
    currentIndex: 0,
  },
}

export const WithThinkingDark: Story = {
  name: 'WithThinking (Dark)',
  args: {
    turns: [makeTurn(
      'RAG 系統能顯著改善大型語言模型的準確率。',
      { thinking: '讓我仔細分析這個問題的各個面向，確保回答全面且準確...' }
    )],
    currentIndex: 0,
  },
  decorators: [withDarkMode],
}

export const MultiTurnWithPager: Story = {
  name: 'Multiple turns (pager visible)',
  args: {
    turns: [
      makeTurn('RAG 是 Retrieval-Augmented Generation 的縮寫。', { userContent: '什麼是 RAG？' }),
      makeTurn('主要優勢是減少幻覺、保持知識最新、無需重新訓練模型。', { userContent: '它的優點是什麼？' }),
    ],
    currentIndex: 1,
  },
}
