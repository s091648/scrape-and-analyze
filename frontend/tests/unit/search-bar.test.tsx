import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { ComponentType } from 'react'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string) => {
      const map: Record<string, string> = {
        'search.placeholder': 'Search articles...',
        'search.noSuggestions': 'No suggestions',
      }
      return map[key] ?? key
    },
  }),
}))

const { mockFetchAutocompleteSuggestions } = vi.hoisted(() => ({
  mockFetchAutocompleteSuggestions: vi.fn(),
}))
vi.mock('@/lib/api/search', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/search')>()
  return { ...actual, fetchAutocompleteSuggestions: mockFetchAutocompleteSuggestions }
})

// A highlighted term's text is split across a <mark> + sibling text nodes, so a plain
// string query (even with { exact: false }) won't match the wrapping <span> — RTL only
// matches an element whose own text content (ignoring descendants) contains the string.
// Match on the element's full textContent instead.
function findByTerm(term: string) {
  return screen.findByText((_content, element) => element?.textContent === term)
}
function queryByTerm(term: string) {
  return screen.queryByText((_content, element) => element?.textContent === term)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let SearchBar: ComponentType<any>

beforeAll(async () => {
  const module = await import('@/components/features/articles/search-bar')
  SearchBar = module.SearchBar as any
})

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchAutocompleteSuggestions.mockResolvedValue({ suggestions: [] })
  // cmdk calls scrollIntoView internally; jsdom doesn't implement it
  Element.prototype.scrollIntoView = vi.fn()
})

describe('SearchBar', () => {
  it('renders the current value', () => {
    render(<SearchBar value="machine learning" onSubmit={vi.fn()} onClear={vi.fn()} />)
    expect(screen.getByPlaceholderText('Search articles...')).toHaveValue('machine learning')
  })

  it('calls onSubmit with the trimmed query on Enter', () => {
    const onSubmit = vi.fn()
    render(<SearchBar value="" onSubmit={onSubmit} onClear={vi.fn()} />)
    const input = screen.getByPlaceholderText('Search articles...')
    fireEvent.change(input, { target: { value: '  machine learning  ' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onSubmit).toHaveBeenCalledWith('machine learning')
  })

  it('does not submit an empty/whitespace-only query on Enter', () => {
    const onSubmit = vi.fn()
    const onClear = vi.fn()
    render(<SearchBar value="" onSubmit={onSubmit} onClear={onClear} />)
    const input = screen.getByPlaceholderText('Search articles...')
    fireEvent.change(input, { target: { value: '   ' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onSubmit).not.toHaveBeenCalled()
    expect(onClear).toHaveBeenCalled()
  })

  it('calls onClear when the input is emptied after previously having a value', () => {
    const onClear = vi.fn()
    render(<SearchBar value="machine learning" onSubmit={vi.fn()} onClear={onClear} />)
    const input = screen.getByPlaceholderText('Search articles...')
    fireEvent.change(input, { target: { value: '' } })
    expect(onClear).toHaveBeenCalled()
  })

  it('does not call onSubmit on non-Enter keys', () => {
    const onSubmit = vi.fn()
    render(<SearchBar value="" onSubmit={onSubmit} onClear={vi.fn()} />)
    const input = screen.getByPlaceholderText('Search articles...')
    fireEvent.change(input, { target: { value: 'test' } })
    fireEvent.keyDown(input, { key: 'a' })
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('syncs the input when the external value prop changes', () => {
    const { rerender } = render(<SearchBar value="" onSubmit={vi.fn()} onClear={vi.fn()} />)
    rerender(<SearchBar value="updated" onSubmit={vi.fn()} onClear={vi.fn()} />)
    expect(screen.getByPlaceholderText('Search articles...')).toHaveValue('updated')
  })

  // ── Autocomplete (023-article-search US2) ─────────────────────────────────

  it('fetches and renders suggestions as the user types', async () => {
    mockFetchAutocompleteSuggestions.mockResolvedValue({
      suggestions: [{ term: 'learning', occurrence_count: 42 }],
    })
    render(<SearchBar value="" onSubmit={vi.fn()} onClear={vi.fn()} topicId="topic-1" />)
    const input = screen.getByPlaceholderText('Search articles...')

    fireEvent.change(input, { target: { value: 'lear' } })

    await waitFor(() => expect(mockFetchAutocompleteSuggestions).toHaveBeenCalledWith(
      'lear', 'topic-1', undefined, undefined, expect.anything(),
    ))
    // "learning" renders split across nodes once the "lear" match is highlighted
    // (see autocomplete-dropdown.test.tsx for dedicated highlight-behavior coverage).
    expect(await findByTerm('learning')).toBeInTheDocument()
  })

  it('does not fetch suggestions for an empty query', () => {
    render(<SearchBar value="" onSubmit={vi.fn()} onClear={vi.fn()} />)
    expect(mockFetchAutocompleteSuggestions).not.toHaveBeenCalled()
  })

  it('skips fetching once the typed text exceeds the max autocomplete query length', () => {
    render(<SearchBar value="" onSubmit={vi.fn()} onClear={vi.fn()} />)
    const input = screen.getByPlaceholderText('Search articles...')

    fireEvent.change(input, { target: { value: 'a'.repeat(9) } }) // cap is 8

    expect(mockFetchAutocompleteSuggestions).not.toHaveBeenCalled()
  })

  it('selecting a suggestion submits a search for that term and closes the dropdown', async () => {
    mockFetchAutocompleteSuggestions.mockResolvedValue({
      suggestions: [{ term: 'learning', occurrence_count: 42 }],
    })
    const onSubmit = vi.fn()
    render(<SearchBar value="" onSubmit={onSubmit} onClear={vi.fn()} />)
    const input = screen.getByPlaceholderText('Search articles...')
    fireEvent.change(input, { target: { value: 'lear' } })
    const suggestion = await findByTerm('learning')

    fireEvent.click(suggestion)

    expect(onSubmit).toHaveBeenCalledWith('learning')
    await waitFor(() => expect(queryByTerm('learning')).not.toBeInTheDocument())
  })
})
