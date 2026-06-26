import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { fn } from 'storybook/test'
import { FloatingChatbotPanel } from '../components/features/chat/FloatingChatbotPanel'
import { withDarkMode } from './decorators'

const meta: Meta<typeof FloatingChatbotPanel> = {
  title: 'Features/Chat/FloatingChatbotPanel',
  component: FloatingChatbotPanel,
  parameters: {
    nextjs: { appDirectory: true },
    layout: 'fullscreen',
  },
  args: {
    messages: [],
    messageSources: {},
    messageAttachments: {},
    onSend: fn(),
    onNewChat: fn(),
    onAbort: fn(),
    onOpenChange: fn(),
    isLoading: false,
    open: false,
    title: 'AI 研究助理',
    placeholder: '詢問 AI：最近有哪些相關研究？',
    theme: 'auto',
  },
}
export default meta
type Story = StoryObj<typeof FloatingChatbotPanel>

export const Closed: Story = {
  args: { open: false },
}

export const OpenEmpty: Story = {
  args: { open: true },
}

export const WithConversation: Story = {
  args: {
    open: true,
    messages: [
      { id: '1', role: 'user', content: '最近有哪些 RAG 研究？', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content:
          '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法的效果。\n\n2. **Self-RAG** — 自省式檢索增強生成，效果顯著提升。',
        timestamp: new Date(),
      },
      { id: '3', role: 'user', content: '這些論文有什麼共同點？', timestamp: new Date() },
    ],
  },
}

export const Loading: Story = {
  args: {
    open: true,
    isLoading: true,
    messages: [
      { id: '1', role: 'user', content: '請問最新的 LLM 研究？', timestamp: new Date() },
    ],
  },
}

export const WithSources: Story = {
  args: {
    open: true,
    messages: [
      { id: '1', role: 'user', content: '請推薦相關論文', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content:
          '以下是資料庫中最相關的文章：\n\n[1] 提出了新型 RAG 架構，在知識密集型任務上優於 fine-tuning。\n\n[2] 則是站內整理的實作筆記，適合入門參考。',
        timestamp: new Date(),
      },
    ],
    messageSources: {
      '2': [
        {
          id: 'src-1',
          url: 'https://arxiv.org/abs/2310.11511',
          title: 'Self-RAG: Learning to Retrieve, Generate, and Critique',
          public_article_id: null,
        },
        {
          id: 'src-2',
          url: 'https://example.com/article/rag-notes',
          title: 'RAG 系統實作筆記',
          public_article_id: 'pub-abc123',
        },
      ],
    },
  },
}

export const WithPinnedArticles: Story = {
  args: {
    open: true,
    messages: [],
    pinnedArticles: [
      { id: 'art-1', title: 'Attention Is All You Need' },
      { id: 'art-2', title: 'Chain-of-Thought Prompting Elicits Reasoning in Large Language Models' },
    ],
    onRemovePinnedArticle: fn(),
  },
}

export const WithPinnedAndConversation: Story = {
  name: 'WithPinnedArticles + Conversation',
  args: {
    open: true,
    messages: [
      { id: '1', role: 'user', content: '這兩篇論文的共同點是什麼？', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content: '這兩篇論文都是 Transformer 架構的重要里程碑：\n\n**Attention Is All You Need** 提出了純注意力機制，完全取代了 RNN。\n\n**Chain-of-Thought** 則展示了透過逐步推理來大幅提升 LLM 的複雜任務能力。',
        timestamp: new Date(),
      },
    ],
    messageAttachments: {
      '1': [
        { id: 'art-1', title: 'Attention Is All You Need' },
        { id: 'art-2', title: 'Chain-of-Thought Prompting Elicits Reasoning in Large Language Models' },
      ],
    },
    messageSources: {},
    onRemovePinnedArticle: fn(),
  },
}

export const WithThinking: Story = {
  name: 'WithThinking (collapsed by default)',
  args: {
    open: true,
    messages: [
      { id: '1', role: 'user', content: '請解釋 RAG 系統的運作原理', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content:
          'RAG（檢索增強生成）系統透過以下步驟運作：\n\n1. **檢索**：根據使用者問題從向量資料庫找出相關文件\n2. **增強**：將檢索到的文件作為上下文加入 prompt\n3. **生成**：LLM 根據上下文生成準確的回答',
        thinking:
          '使用者問的是 RAG 系統的原理，這是一個技術性問題。\n\n讓我逐步拆解：\n\n**R - Retrieval（檢索）**\n- 使用者輸入被轉換為向量嵌入\n- 從向量資料庫中計算相似度並檢索 top-k 文件\n\n**A - Augmented（增強）**\n- 將檢索到的文件片段插入 prompt template\n\n**G - Generation（生成）**\n- LLM 基於增強後的 prompt 生成回答\n- 可加入 citation 讓使用者追溯來源',
        timestamp: new Date(),
      },
    ],
  },
}

// ─── Dark mode ───────────────────────────────────────────────────────────────

export const ClosedDark: Story = {
  name: 'Closed (Dark)',
  decorators: [withDarkMode],
  args: { open: false },
}

export const WithConversationDark: Story = {
  name: 'WithConversation (Dark)',
  decorators: [withDarkMode],
  args: {
    open: true,
    messages: [
      { id: '1', role: 'user', content: '最近有哪些 RAG 研究？', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content:
          '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法的效果。\n\n2. **Self-RAG** — 自省式檢索增強生成，效果顯著提升。',
        timestamp: new Date(),
      },
    ],
  },
}

export const WithSourcesDark: Story = {
  name: 'WithSources (Dark)',
  decorators: [withDarkMode],
  args: {
    open: true,
    messages: [
      { id: '1', role: 'user', content: '請推薦相關論文', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content: '以下是最相關的文章：\n\n[1] Self-RAG 在知識密集型任務上表現卓越。\n\n[2] 站內筆記提供了實作細節。',
        timestamp: new Date(),
      },
    ],
    messageSources: {
      '2': [
        {
          id: 'src-1',
          url: 'https://arxiv.org/abs/2310.11511',
          title: 'Self-RAG: Learning to Retrieve, Generate, and Critique',
          public_article_id: null,
        },
        {
          id: 'src-2',
          url: 'https://example.com/article/rag-notes',
          title: 'RAG 系統實作筆記',
          public_article_id: 'pub-abc123',
        },
      ],
    },
  },
}

export const WithPinnedArticlesDark: Story = {
  name: 'WithPinnedArticles (Dark)',
  decorators: [withDarkMode],
  args: {
    open: true,
    messages: [],
    pinnedArticles: [
      { id: 'art-1', title: 'Attention Is All You Need' },
      { id: 'art-2', title: 'Chain-of-Thought Prompting Elicits Reasoning in Large Language Models' },
    ],
    onRemovePinnedArticle: fn(),
  },
}

export const WithThinkingDark: Story = {
  name: 'WithThinking (Dark)',
  decorators: [withDarkMode],
  args: {
    open: true,
    messages: [
      { id: '1', role: 'user', content: '請解釋 RAG 系統的運作原理', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content: 'RAG 系統透過檢索、增強、生成三步驟提升回答品質。',
        thinking: '讓我仔細思考這個問題的最佳解釋方式，確保涵蓋關鍵概念...',
        timestamp: new Date(),
      },
    ],
  },
}
