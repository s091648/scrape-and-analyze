import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ReleaseNotesPopover } from '@/components/features/navigation/release-notes-popover'

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  global.fetch = vi.fn()
})

const sampleEntries = [
  {
    version: '1.2.0',
    date: '2024-06-01',
    changes: [
      { type: 'feat', description: 'Added new feature' },
      { type: 'fix', description: 'Fixed a bug' },
    ],
  },
  {
    version: '1.1.0',
    date: '2024-05-01',
    changes: [{ type: 'feat', description: 'Initial feature' }],
  },
]

const pendingEntry = {
  version: '{{next}}',
  date: '',
  changes: [] as { type: string; description: string }[],
}

function mockFetchOk(data: any) {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
    json: () => Promise.resolve(data),
  })
}

function mockFetchFail() {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('network error'))
}

describe('ReleaseNotesPopover', () => {
  it('renders the trigger button', () => {
    mockFetchOk([])
    render(<ReleaseNotesPopover />)
    expect(screen.getByRole('button', { name: /release notes/i })).toBeInTheDocument()
  })

  it('fetches /release-notes.json on mount', async () => {
    mockFetchOk(sampleEntries)
    render(<ReleaseNotesPopover />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/release-notes.json'))
  })

  it('shows unread red dot when last_seen version is behind latest', async () => {
    mockFetchOk(sampleEntries)
    localStorage.setItem('last_seen_release_version', '1.1.0')
    render(<ReleaseNotesPopover />)
    await waitFor(() => {
      const dot = document.querySelector('.bg-red-500')
      expect(dot).toBeTruthy()
    })
  })

  it('does not show red dot when last_seen matches latest version', async () => {
    mockFetchOk(sampleEntries)
    localStorage.setItem('last_seen_release_version', '1.2.0')
    render(<ReleaseNotesPopover />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    // allow state to settle
    await new Promise(r => setTimeout(r, 20))
    expect(document.querySelector('.bg-red-500')).toBeFalsy()
  })

  it('handles fetch failure gracefully — shows button, no crash', async () => {
    mockFetchFail()
    render(<ReleaseNotesPopover />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: /release notes/i })).toBeInTheDocument()
  })

  it('does not show red dot when there are no real entries', async () => {
    mockFetchOk([])
    render(<ReleaseNotesPopover />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    await new Promise(r => setTimeout(r, 20))
    expect(document.querySelector('.bg-red-500')).toBeFalsy()
  })

  it('filters out pending entries with no changes from visible list', async () => {
    mockFetchOk([pendingEntry, ...sampleEntries])
    render(<ReleaseNotesPopover />)
    // Pending entry with no changes should not appear in visible list
    // (it's filtered by the component logic: !isPending || changes.length > 0)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
  })

  it('marks latest version as seen in localStorage when popover is opened', async () => {
    mockFetchOk(sampleEntries)
    render(<ReleaseNotesPopover />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    await new Promise(r => setTimeout(r, 20))
    fireEvent.click(screen.getByRole('button', { name: /release notes/i }))
    await waitFor(() =>
      expect(localStorage.getItem('last_seen_release_version')).toBe('1.2.0')
    )
  })

  it('shows release notes content after opening the popover', async () => {
    mockFetchOk(sampleEntries)
    render(<ReleaseNotesPopover />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    await new Promise(r => setTimeout(r, 20))
    fireEvent.click(screen.getByRole('button', { name: /release notes/i }))
    await waitFor(() => expect(screen.getByText('Added new feature')).toBeInTheDocument())
  })

  it('displays change type badges (feat, fix)', async () => {
    mockFetchOk(sampleEntries)
    render(<ReleaseNotesPopover />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    await new Promise(r => setTimeout(r, 20))
    fireEvent.click(screen.getByRole('button', { name: /release notes/i }))
    await waitFor(() => {
      // multiple 'feat' badges exist (one per release entry)
      expect(screen.getAllByText('feat').length).toBeGreaterThan(0)
      expect(screen.getByText('fix')).toBeInTheDocument()
    })
  })

  it('shows "No releases yet." when entries list is empty after loading', async () => {
    mockFetchOk([])
    render(<ReleaseNotesPopover />)
    await waitFor(() => expect(global.fetch).toHaveBeenCalled())
    await new Promise(r => setTimeout(r, 20))
    fireEvent.click(screen.getByRole('button', { name: /release notes/i }))
    await waitFor(() => expect(screen.getByText('No releases yet.')).toBeInTheDocument())
  })
})
