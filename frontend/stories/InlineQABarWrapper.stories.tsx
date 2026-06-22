import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { fn } from 'storybook/test'
import { InlineQABarWrapper } from '../components/features/chat/InlineQABarWrapper'
import { withDarkMode } from './decorators'

const meta: Meta<typeof InlineQABarWrapper> = {
  title: 'Features/Chat/InlineQABarWrapper',
  component: InlineQABarWrapper,
  parameters: {
    nextjs: { appDirectory: true },
  },
}
export default meta
type Story = StoryObj<typeof InlineQABarWrapper>

export const Default: Story = {
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
}

export const Loading: Story = {
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [
            { id: '1', role: 'user', content: '最近的 LLM 研究？', timestamp: new Date() },
            { id: '2', role: 'assistant', content: '正在查詢中', timestamp: new Date() },
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

export const WithAnswer: Story = {
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [
            { id: '1', role: 'user', content: '最近的 LLM 研究？', timestamp: new Date() },
            {
              id: '2',
              role: 'assistant',
              content:
                '根據近期研究，以下論文值得關注：\n\n1. [Scaling Laws for Neural Language Models](https://arxiv.org/abs/2001.08361) — 探討模型規模與性能的關係。\n\n2. [Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903) — 展示 few-shot 引導鏈式推理的方法。',
              timestamp: new Date(),
            },
          ],
          sendMessage: fn(),
          isLoading: false,
          error: null,
          clearMessages: fn(),
        }),
      },
    },
  },
}

export const RateLimitError: Story = {
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [],
          sendMessage: fn(),
          isLoading: false,
          error: new Error('HTTP 429'),
          clearMessages: fn(),
        }),
      },
    },
  },
}

export const ServiceUnavailableError: Story = {
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [],
          sendMessage: fn(),
          isLoading: false,
          error: new Error('HTTP 503'),
          clearMessages: fn(),
        }),
      },
    },
  },
}

export const DefaultDark: Story = {
  name: 'Default (Dark)',
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  decorators: [withDarkMode],
}

export const WithAnswerDark: Story = {
  name: 'WithAnswer (Dark)',
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  decorators: [withDarkMode],
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [
            { id: '1', role: 'user', content: '最近的 LLM 研究？', timestamp: new Date() },
            {
              id: '2',
              role: 'assistant',
              content:
                '根據近期研究，以下論文值得關注：\n\n1. [Scaling Laws for Neural Language Models](https://arxiv.org/abs/2001.08361) — 探討模型規模與性能的關係。\n\n2. [Chain-of-Thought Prompting](https://arxiv.org/abs/2201.11903) — 展示 few-shot 引導鏈式推理的方法。',
              timestamp: new Date(),
            },
          ],
          sendMessage: fn(),
          isLoading: false,
          error: null,
          clearMessages: fn(),
        }),
      },
    },
  },
}
