import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Command } from '@/components/ui/command'
import { AutocompleteDropdown } from '@/components/features/articles/autocomplete-dropdown'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string) => ({ 'search.noSuggestions': 'No suggestions' })[key] ?? key,
  }),
}))

function renderInCommand(ui: React.ReactElement) {
  return render(
    <Command shouldFilter={false}>{ui}</Command>
  )
}

// A highlighted term's text is split across a <mark> + sibling text nodes, so a plain
// string query (even with { exact: false }) won't match the wrapping <span> — RTL only
// matches an element whose own text content (ignoring descendants) contains the string.
// Match on the element's full textContent instead.
function getByTerm(term: string) {
  return screen.getByText((_content, element) => element?.textContent === term)
}

beforeEach(() => {
  vi.clearAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
})

describe('AutocompleteDropdown', () => {
  it('renders the empty state when there are no suggestions', () => {
    renderInCommand(<AutocompleteDropdown suggestions={[]} onSelect={vi.fn()} query="" />)
    expect(screen.getByText('No suggestions')).toBeInTheDocument()
  })

  it('renders every suggestion term', () => {
    renderInCommand(
      <AutocompleteDropdown
        suggestions={[
          { term: 'learning', occurrence_count: 42 },
          { term: 'language', occurrence_count: 18 },
        ]}
        onSelect={vi.fn()}
        query="l"
      />
    )
    expect(getByTerm('learning')).toBeInTheDocument()
    expect(getByTerm('language')).toBeInTheDocument()
  })

  it('renders each suggestion\'s occurrence_count', () => {
    renderInCommand(
      <AutocompleteDropdown suggestions={[{ term: 'learning', occurrence_count: 42 }]} onSelect={vi.fn()} query="lear" />
    )
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('calls onSelect with the term when a suggestion is clicked', () => {
    const onSelect = vi.fn()
    renderInCommand(
      <AutocompleteDropdown suggestions={[{ term: 'learning', occurrence_count: 42 }]} onSelect={onSelect} query="lear" />
    )
    fireEvent.click(getByTerm('learning'))
    expect(onSelect).toHaveBeenCalledWith('learning')
  })

  it('does not render the empty state when suggestions are present', () => {
    renderInCommand(
      <AutocompleteDropdown suggestions={[{ term: 'learning', occurrence_count: 42 }]} onSelect={vi.fn()} query="lear" />
    )
    expect(screen.queryByText('No suggestions')).not.toBeInTheDocument()
  })

  // ── Match highlighting ──────────────────────────────────────────────────

  it('wraps the matched substring in a <mark>', () => {
    renderInCommand(
      <AutocompleteDropdown suggestions={[{ term: 'learning', occurrence_count: 42 }]} onSelect={vi.fn()} query="lear" />
    )
    const mark = document.querySelector('mark')
    expect(mark).not.toBeNull()
    expect(mark).toHaveTextContent('lear')
  })

  it('highlights the query wherever it occurs, not just at the start (contains-anywhere)', () => {
    renderInCommand(
      <AutocompleteDropdown suggestions={[{ term: 'learning', occurrence_count: 42 }]} onSelect={vi.fn()} query="arn" />
    )
    const mark = document.querySelector('mark')
    expect(mark).toHaveTextContent('arn')
  })

  it('renders plain text with no <mark> when query is empty', () => {
    renderInCommand(
      <AutocompleteDropdown suggestions={[{ term: 'learning', occurrence_count: 42 }]} onSelect={vi.fn()} query="" />
    )
    expect(document.querySelector('mark')).toBeNull()
  })
})
