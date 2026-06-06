import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import { ScraperSourceForm } from '../components/features/scraper/scraper-source-form'

const meta: Meta<typeof ScraperSourceForm> = {
  title: 'Features/Scraper/ScraperSourceForm',
  component: ScraperSourceForm,
  args: {
    onSubmit: () => {},
  },
}
export default meta
type Story = StoryObj<typeof ScraperSourceForm>

export const RssForm: Story = {}

export const PrefilledRss: Story = {
  play: async ({ canvasElement }) => {
    const nameInput = canvasElement.querySelector('#name') as HTMLInputElement
    const urlInput = canvasElement.querySelector('#url') as HTMLInputElement
    if (nameInput) nameInput.value = 'Hacker News'
    if (urlInput) urlInput.value = 'https://news.ycombinator.com/rss'
  },
}
