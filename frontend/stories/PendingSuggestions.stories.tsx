import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { PendingSuggestions } from '../components/features/tags/pending-suggestions'
import type { SuggestionOut } from '../lib/api/tags'

const suggestions: SuggestionOut[] = [
  {
    id: 'sug-1',
    new_tag_id: 'tag-a',
    new_tag_name: 'LLM',
    existing_tag_id: 'tag-b',
    existing_tag_name: 'Large Language Model',
    group_name: 'NLP',
    similarity_score: 0.96,
    article_id: null,
  },
  {
    id: 'sug-2',
    new_tag_id: 'tag-c',
    new_tag_name: 'Transformer Architecture',
    existing_tag_id: 'tag-d',
    existing_tag_name: 'Transformer',
    group_name: 'Machine Learning',
    similarity_score: 0.91,
    article_id: 'art-1',
  },
  {
    id: 'sug-3',
    new_tag_id: 'tag-e',
    new_tag_name: 'RL',
    existing_tag_id: 'tag-f',
    existing_tag_name: 'Reinforcement Learning',
    group_name: 'Machine Learning',
    similarity_score: 0.93,
    article_id: null,
  },
]

const meta: Meta<typeof PendingSuggestions> = {
  title: 'Features/Tags/PendingSuggestions',
  component: PendingSuggestions,
  args: {
    suggestions,
    token: 'mock-token',
    onResolved: () => {},
  },
}
export default meta
type Story = StoryObj<typeof PendingSuggestions>

export const Default: Story = {}

export const Single: Story = {
  args: {
    suggestions: [suggestions[0]],
  },
}

export const Many: Story = {
  args: {
    suggestions: [
      ...suggestions,
      {
        id: 'sug-4',
        new_tag_id: 'tag-g',
        new_tag_name: 'GPT',
        existing_tag_id: 'tag-h',
        existing_tag_name: 'GPT-4',
        group_name: 'NLP',
        similarity_score: 0.92,
        article_id: null,
      },
      {
        id: 'sug-5',
        new_tag_id: 'tag-i',
        new_tag_name: 'BERT',
        existing_tag_id: 'tag-j',
        existing_tag_name: 'BERT Model',
        group_name: 'NLP',
        similarity_score: 0.90,
        article_id: null,
      },
    ],
  },
}
