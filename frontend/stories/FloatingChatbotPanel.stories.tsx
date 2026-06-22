import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { fn } from 'storybook/test'
import { userEvent, within } from '@storybook/test'
import { FloatingChatbotPanel } from '../components/features/chat/FloatingChatbotPanel'
import { withDarkMode } from './decorators'

const meta: Meta<typeof FloatingChatbotPanel> = {
  title: 'Features/RAG/FloatingChatbotPanel',
  component: FloatingChatbotPanel,
  parameters: {
    nextjs: { appDirectory: true },
    layout: 'fullscreen',
  },
  args: {
    messages: [],
    messageSources: {},
    onSend: fn(),
    isLoading: false,
    title: 'AI 助理',
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
}
export default meta
type Story = StoryObj<typeof FloatingChatbotPanel>

const openPanel = async (canvasElement: HTMLElement) => {
  const canvas = within(canvasElement)
  await userEvent.click(canvas.getByRole('button', { name: 'Open chat' }))
}

export const Default: Story = {}

export const Opened: Story = {
  play: async ({ canvasElement }) => {
    await openPanel(canvasElement)
  },
}

export const WithConversation: Story = {
  args: {
    messages: [
      { id: '1', role: 'user', content: '最近有哪些 RAG 研究？', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content:
          '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法。\n\n2. **Self-RAG** — 自省式檢索增強生成，效果顯著提升。',
        timestamp: new Date(),
      },
      { id: '3', role: 'user', content: '這些論文有什麼共同點？', timestamp: new Date() },
    ],
    onNewChat: fn(),
  },
  play: async ({ canvasElement }) => {
    await openPanel(canvasElement)
  },
}

export const WithSources: Story = {
  args: {
    messages: [
      { id: '1', role: 'user', content: '請推薦相關論文', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content: '以下是相關文章：',
        timestamp: new Date(),
      },
    ],
    messageSources: {
      '2': [
        { id: 's1', title: 'Self-RAG: Learning to Retrieve', url: 'https://arxiv.org/abs/2310.11511', public_article_id: null },
        { id: 's2', title: '站內文章：RAG 實踐筆記', url: 'https://example.com/article/1', public_article_id: 'pub-abc123' },
      ],
    },
  },
  parameters: {
    moduleMock: {
      '@/lib/api/articles': {
        fetchArticleById: async () => ({
          title: 'RAG 實踐筆記',
          content: '本文介紹如何在生產環境實作 RAG 系統。',
          url: 'https://example.com/article/1',
          source: 'Internal',
          published_at: '2024-06-01',
          via_source: null,
          original_source: null,
        }),
      },
    },
  },
  play: async ({ canvasElement }) => {
    await openPanel(canvasElement)
  },
}

export const Loading: Story = {
  args: {
    messages: [
      { id: '1', role: 'user', content: '請問最新的 LLM 研究？', timestamp: new Date() },
    ],
    isLoading: true,
  },
  play: async ({ canvasElement }) => {
    await openPanel(canvasElement)
  },
}

export const DefaultDark: Story = {
  name: 'Default (Dark)',
  decorators: [withDarkMode],
  play: async ({ canvasElement }) => {
    await openPanel(canvasElement)
  },
}

export const WithConversationDark: Story = {
  name: 'WithConversation (Dark)',
  args: {
    messages: [
      { id: '1', role: 'user', content: '最近有哪些 RAG 研究？', timestamp: new Date() },
      {
        id: '2',
        role: 'assistant',
        content:
          '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法。\n\n2. **Self-RAG** — 自省式檢索增強生成，效果顯著提升。',
        timestamp: new Date(),
      },
    ],
    onNewChat: fn(),
  },
  decorators: [withDarkMode],
  play: async ({ canvasElement }) => {
    await openPanel(canvasElement)
  },
}
