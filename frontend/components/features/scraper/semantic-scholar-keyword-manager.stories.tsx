import type { Meta, StoryObj } from '@storybook/react'
import { SemanticScholarKeywordManager } from './semantic-scholar-keyword-manager'

const meta: Meta<typeof SemanticScholarKeywordManager> = {
  title: 'Features/Scraper/SemanticScholarKeywordManager',
  component: SemanticScholarKeywordManager,
}
export default meta

type Story = StoryObj<typeof SemanticScholarKeywordManager>

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
