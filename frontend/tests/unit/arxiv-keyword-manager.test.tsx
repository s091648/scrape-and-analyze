import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { I18nProvider } from '@/lib/providers/i18n-provider'
import { ArxivKeywordManager } from '@/components/features/scraper/arxiv-keyword-manager'

const defaultProps = {
  keywords: [] as { id: string; keyword: string }[],
  categories: [] as { id: string; keyword: string }[],
  onAddKeyword: vi.fn().mockResolvedValue(undefined),
  onDeleteKeyword: vi.fn().mockResolvedValue(undefined),
  onAddCategory: vi.fn().mockResolvedValue(undefined),
  onDeleteCategory: vi.fn().mockResolvedValue(undefined),
}

function renderManager(overrides: Partial<typeof defaultProps> = {}) {
  const props = { ...defaultProps, ...overrides }
  return render(
    <I18nProvider>
      <ArxivKeywordManager {...props} />
    </I18nProvider>
  )
}

beforeEach(() => vi.clearAllMocks())

describe('ArxivKeywordManager', () => {
  it('renders without crashing', () => {
    renderManager()
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('shows "no keywords yet" empty state when keyword list is empty', () => {
    renderManager()
    expect(screen.getByText(/no keywords yet/i)).toBeInTheDocument()
  })

  it('shows "no categories" empty state when category list is empty', () => {
    renderManager()
    expect(screen.getByText(/no categories/i)).toBeInTheDocument()
  })

  it('renders existing keywords as chips with field label and value', () => {
    renderManager({ keywords: [{ id: '1', keyword: 'ti:robot' }] })
    expect(screen.getAllByText('Title').length).toBeGreaterThan(0)
    expect(screen.getByText('robot')).toBeInTheDocument()
  })

  it('parses quoted keyword value correctly', () => {
    renderManager({ keywords: [{ id: '1', keyword: 'ti:"digital twin"' }] })
    expect(screen.getByText('digital twin')).toBeInTheDocument()
  })

  it('renders abstract field label for abs: prefix', () => {
    renderManager({ keywords: [{ id: '1', keyword: 'abs:transformer' }] })
    // multiple "Abstract" texts exist (chip label + select option)
    const matches = screen.getAllByText('Abstract')
    expect(matches.length).toBeGreaterThan(0)
  })

  it('renders existing categories as chips', () => {
    renderManager({ categories: [{ id: 'c1', keyword: 'cs.AI' }] })
    expect(screen.getByText('cs.AI')).toBeInTheDocument()
  })

  it('calls onDeleteKeyword when keyword remove button is clicked', async () => {
    const onDeleteKeyword = vi.fn().mockResolvedValue(undefined)
    renderManager({
      keywords: [{ id: 'k1', keyword: 'abs:transformer' }],
      onDeleteKeyword,
    })
    fireEvent.click(screen.getByLabelText(/remove abs:transformer/i))
    await waitFor(() => expect(onDeleteKeyword).toHaveBeenCalledWith('k1'))
  })

  it('calls onDeleteCategory when category remove button is clicked', async () => {
    const onDeleteCategory = vi.fn().mockResolvedValue(undefined)
    renderManager({
      categories: [{ id: 'c1', keyword: 'cs.LG' }],
      onDeleteCategory,
    })
    fireEvent.click(screen.getByLabelText(/remove category cs.LG/i))
    await waitFor(() => expect(onDeleteCategory).toHaveBeenCalledWith('c1'))
  })

  it('calls onAddKeyword with serialized keyword when Enter is pressed', async () => {
    const onAddKeyword = vi.fn().mockResolvedValue(undefined)
    renderManager({ onAddKeyword })
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'robotics' } })
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' })
    await waitFor(() => expect(onAddKeyword).toHaveBeenCalledWith('ti:robotics'))
  })

  it('serializes multi-word keyword with quotes', async () => {
    const onAddKeyword = vi.fn().mockResolvedValue(undefined)
    renderManager({ onAddKeyword })
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'neural network' } })
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' })
    await waitFor(() => expect(onAddKeyword).toHaveBeenCalledWith('ti:"neural network"'))
  })

  it('does not call onAddKeyword when input is empty', async () => {
    const onAddKeyword = vi.fn()
    renderManager({ onAddKeyword })
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' })
    expect(onAddKeyword).not.toHaveBeenCalled()
  })

  it('clears keyword input after successful add', async () => {
    const onAddKeyword = vi.fn().mockResolvedValue(undefined)
    renderManager({ onAddKeyword })
    const input = screen.getByRole('textbox') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'test' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(input.value).toBe(''))
  })

  it('shows preview text with serialized keyword while typing', () => {
    renderManager()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'digital twin' } })
    expect(screen.getByText('ti:"digital twin"')).toBeInTheDocument()
  })

  it('does not show preview text when input is empty', () => {
    renderManager()
    expect(screen.queryByText(/stores as/i)).not.toBeInTheDocument()
  })

  it('shows query preview when categories are present', () => {
    renderManager({ categories: [{ id: 'c1', keyword: 'cs.AI' }, { id: 'c2', keyword: 'cs.LG' }] })
    expect(screen.getByText(/cat:cs\.AI OR cat:cs\.LG/)).toBeInTheDocument()
  })
})
