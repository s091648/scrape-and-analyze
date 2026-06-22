import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { fn } from 'storybook/test'
import { FloatingChatbotWrapper } from '../components/features/chat/FloatingChatbotWrapper'
import { withDarkMode } from './decorators'

const meta: Meta<typeof FloatingChatbotWrapper> = {
  title: 'Features/Chat/FloatingChatbotWrapper',
  component: FloatingChatbotWrapper,
  parameters: {
    nextjs: { appDirectory: true },
    layout: 'fullscreen',
  },
}
export default meta
type Story = StoryObj<typeof FloatingChatbotWrapper>

export const Default: Story = {}

export const WithConversation: Story = {
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [
            { id: '1', role: 'user', content: '最近有哪些 RAG 研究？', timestamp: new Date() },
            {
              id: '2',
              role: 'assistant',
              content:
                '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法的效果。\n\n2. [Self-RAG](https://arxiv.org/abs/2310.11511) — 自省式檢索增強生成。',
              timestamp: new Date(),
            },
            { id: '3', role: 'user', content: '這些論文有什麼共同點？', timestamp: new Date() },
          ],
          sendMessage: fn(),
          isLoading: true,
          error: null,
          clearMessages: fn(),
        }),
      },
    },
  },
}

export const Loading: Story = {
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [
            { id: '1', role: 'user', content: '你好！', timestamp: new Date() },
          ],
          sendMessage: fn(),
          isLoading: true,
          error: null,
          clearMessages: fn(),
        }),
      },
    },
  },
}

export const RateLimitError: Story = {
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: (opts: any) => {
          opts?.onError?.(new Error('HTTP 429'))
          return {
            messages: [],
            sendMessage: fn(),
            isLoading: false,
            error: null,
            clearMessages: fn(),
          }
        },
      },
    },
  },
}

export const DefaultDark: Story = {
  name: 'Default (Dark)',
  decorators: [withDarkMode],
}

export const WithConversationDark: Story = {
  name: 'WithConversation (Dark)',
  decorators: [withDarkMode],
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [
            { id: '1', role: 'user', content: '最近有哪些 RAG 研究？', timestamp: new Date() },
            {
              id: '2',
              role: 'assistant',
              content:
                '根據近期研究：\n\n1. [RAG vs Fine-Tuning](https://arxiv.org/abs/2401.00001) — 比較兩種方法的效果。\n\n2. [Self-RAG](https://arxiv.org/abs/2310.11511) — 自省式檢索增強生成。',
              timestamp: new Date(),
            },
            { id: '3', role: 'user', content: '這些論文有什麼共同點？', timestamp: new Date() },
          ],
          sendMessage: fn(),
          isLoading: true,
          error: null,
          clearMessages: fn(),
        }),
      },
    },
  },
}
