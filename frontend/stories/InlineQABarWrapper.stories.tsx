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

export const WithThinking: Story = {
  name: 'WithThinking (collapsed by default)',
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [
            { id: '1', role: 'user', content: '什麼是 Chain-of-Thought prompting？', timestamp: new Date() },
            {
              id: '2',
              role: 'assistant',
              content:
                'Chain-of-Thought（CoT）prompting 是一種提示工程技術，透過引導模型逐步推理來提升複雜任務的準確率。',
              thinking:
                '使用者問的是 CoT prompting 技術。\n\n讓我回顧關鍵知識點：\n\n1. CoT 由 Wei et al. (2022) 提出，在 few-shot 設定中展示推理步驟\n2. 標準 prompting 直接輸出答案；CoT 先展示推理再給答案\n3. 對於數學、邏輯、常識推理任務效果最佳\n4. Zero-shot CoT 只需加入 "Let\'s think step by step"\n5. 在大型模型（100B+）上效果更為顯著\n\n結論：這是一個相對清晰的問題，可以給出簡潔但完整的解釋。',
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

export const WithThinkingDark: Story = {
  name: 'WithThinking (Dark)',
  args: {
    placeholder: '詢問 AI：最近有哪些相關研究？',
  },
  decorators: [withDarkMode],
  parameters: {
    moduleMock: {
      '@s091648/chatbot-plugin-ui': {
        useChat: () => ({
          messages: [
            { id: '1', role: 'user', content: '什麼是 Chain-of-Thought prompting？', timestamp: new Date() },
            {
              id: '2',
              role: 'assistant',
              content: 'Chain-of-Thought prompting 透過引導模型逐步推理來提升複雜任務的準確率。',
              thinking: '讓我仔細分析 CoT 的核心機制與優缺點...',
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
