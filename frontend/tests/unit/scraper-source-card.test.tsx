import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { formatFrequency, formatCountdown } from '@/components/features/scraper/scraper-source-card'

const settingFixture = {
  id: 's1',
  source_type: 'rss' as const,
  name: 'Hacker News',
  url: 'https://news.ycombinator.com/rss',
  frequency: 24,
  is_active: true,
  last_scraped_at: null,
  activity: [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1],
}

describe('formatFrequency', () => {
  it('returns "12h" for sub-24h frequency', () => {
    expect(formatFrequency(12)).toBe('12h')
  })

  it('returns "24h (= 1d)" for exactly 24h', () => {
    expect(formatFrequency(24)).toBe('24h (= 1d)')
  })

  it('returns "36h (= 1d 12h)" for 36h', () => {
    expect(formatFrequency(36)).toBe('36h (= 1d 12h)')
  })
})

describe('formatCountdown', () => {
  it('returns "due now" for 0ms', () => {
    expect(formatCountdown(0)).toBe('due now')
  })

  it('returns "due now" for negative ms', () => {
    expect(formatCountdown(-100)).toBe('due now')
  })

  it('formats hours and minutes', () => {
    // 1h 30m 0s = 5400000ms
    expect(formatCountdown(5400000)).toBe('1h:30m:00s')
  })
})

describe('SourceCard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders source name and type', async () => {
    const { SourceCard } = await import('@/components/features/scraper/scraper-source-card')
    render(<SourceCard setting={settingFixture} onUpdate={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('Hacker News')).toBeInTheDocument()
  })

  it('shows "active" badge when is_active is true', async () => {
    const { SourceCard } = await import('@/components/features/scraper/scraper-source-card')
    render(<SourceCard setting={settingFixture} onUpdate={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('active')).toBeInTheDocument()
  })

  it('shows "inactive" badge when is_active is false', async () => {
    const { SourceCard } = await import('@/components/features/scraper/scraper-source-card')
    render(<SourceCard setting={{ ...settingFixture, is_active: false }} onUpdate={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('inactive')).toBeInTheDocument()
  })

  it('clicking active badge calls onUpdate with toggled is_active', async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined)
    const { SourceCard } = await import('@/components/features/scraper/scraper-source-card')
    render(<SourceCard setting={settingFixture} onUpdate={onUpdate} onDelete={vi.fn()} />)
    fireEvent.click(screen.getByText('active'))
    expect(onUpdate).toHaveBeenCalledWith('s1', { is_active: false })
  })

  it('ActivityGraph renders bars for non-zero activity data', async () => {
    const { ActivityGraph } = await import('@/components/features/scraper/scraper-source-card')
    render(<ActivityGraph activity={[0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1]} />)
    const bars = document.querySelectorAll('[title*="article"]')
    expect(bars.length).toBe(14)
  })
})
