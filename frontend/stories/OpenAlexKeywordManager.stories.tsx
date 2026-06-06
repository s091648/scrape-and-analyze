import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { OpenAlexKeywordManager } from '../components/features/scraper/openalex-keyword-manager'

const meta: Meta<typeof OpenAlexKeywordManager> = {
  title: 'Features/Scraper/OpenAlexKeywordManager',
  component: OpenAlexKeywordManager,
}
export default meta

type Story = StoryObj<typeof OpenAlexKeywordManager>

export const Empty: Story = {
  args: {
    keywords: [],
    onAdd: async () => {},
    onDelete: async () => {},
  },
}

export const WithKeywords: Story = {
  args: {
    keywords: [
      { id: '1', keyword: 'digital twin' },
      { id: '2', keyword: 'cyber-physical systems' },
      { id: '3', keyword: 'reinforcement learning' },
    ],
    onAdd: async () => {},
    onDelete: async () => {},
  },
}
