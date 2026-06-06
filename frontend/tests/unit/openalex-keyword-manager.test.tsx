import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { I18nProvider } from '@/lib/providers/i18n-provider'
import { OpenAlexKeywordManager } from '@/components/features/scraper/openalex-keyword-manager'

const renderManager = (props: {
  keywords?: { id: string; keyword: string }[]
  onAdd?: (kw: string) => Promise<void>
  onDelete?: (id: string) => Promise<void>
}) => {
  const defaults = {
    keywords: [],
    onAdd: vi.fn().mockResolvedValue(undefined),
    onDelete: vi.fn().mockResolvedValue(undefined),
  }
  return render(
    <I18nProvider>
      <OpenAlexKeywordManager {...defaults} {...props} />
    </I18nProvider>
  )
}

describe('OpenAlexKeywordManager', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the section heading', () => {
    renderManager({})
    expect(screen.getByText(/search keywords/i)).toBeInTheDocument()
  })

  it('shows empty state when no keywords', () => {
    renderManager({ keywords: [] })
    expect(screen.getByText(/no keywords yet/i)).toBeInTheDocument()
  })

  it('renders existing keywords as chips', () => {
    renderManager({
      keywords: [
        { id: '1', keyword: 'digital twin' },
        { id: '2', keyword: 'iot' },
      ],
    })
    expect(screen.getByText('digital twin')).toBeInTheDocument()
    expect(screen.getByText('iot')).toBeInTheDocument()
  })

  it('calls onDelete when X button is clicked', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined)
    renderManager({
      keywords: [{ id: 'kw1', keyword: 'digital twin' }],
      onDelete,
    })
    const removeBtn = screen.getByLabelText(/remove digital twin/i)
    fireEvent.click(removeBtn)
    await waitFor(() => expect(onDelete).toHaveBeenCalledWith('kw1'))
  })

  it('calls onAdd when Add button is clicked with non-empty input', async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined)
    renderManager({ onAdd })

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'neural rendering' } })
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => expect(onAdd).toHaveBeenCalledWith('neural rendering'))
  })

  it('calls onAdd when Enter is pressed', async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined)
    renderManager({ onAdd })

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'smart city' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    await waitFor(() => expect(onAdd).toHaveBeenCalledWith('smart city'))
  })

  it('does not call onAdd when input is empty', async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined)
    renderManager({ onAdd })

    fireEvent.click(screen.getByRole('button'))
    expect(onAdd).not.toHaveBeenCalled()
  })

  it('clears input after successful add', async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined)
    renderManager({ onAdd })

    const input = screen.getByRole('textbox') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'machine learning' } })
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => expect(input.value).toBe(''))
  })

  it('trims whitespace before calling onAdd', async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined)
    renderManager({ onAdd })

    fireEvent.change(screen.getByRole('textbox'), { target: { value: '  digital twin  ' } })
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => expect(onAdd).toHaveBeenCalledWith('digital twin'))
  })
})
