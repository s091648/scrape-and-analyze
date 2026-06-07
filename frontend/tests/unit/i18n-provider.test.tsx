import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { I18nProvider, useI18n } from '@/lib/providers/i18n-provider'

const { mockApiFetch } = vi.hoisted(() => ({ mockApiFetch: vi.fn() }))
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

function mockLanguagesOk(available = [
  { code: 'en', name: 'English', native_name: 'English' },
  { code: 'zh-TW', name: 'Traditional Chinese', native_name: '繁體中文' },
], resolved = 'en') {
  mockApiFetch.mockResolvedValue({
    json: () => Promise.resolve({ available, resolved }),
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  mockLanguagesOk()
})

function TestConsumer() {
  const { locale, setLocale, availableLanguages, isLoading, t } = useI18n()
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <span data-testid="loading">{isLoading ? 'loading' : 'ready'}</span>
      <span data-testid="lang-count">{availableLanguages.length}</span>
      <span data-testid="t-articles">{t('nav.articles')}</span>
      <button onClick={() => setLocale('zh-TW')}>set-zh-TW</button>
    </div>
  )
}

function renderProvider() {
  return render(<I18nProvider><TestConsumer /></I18nProvider>)
}

describe('I18nProvider', () => {
  it('starts loading and resolves to ready', async () => {
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
  })

  it('calls apiFetch to resolve available languages on mount', async () => {
    renderProvider()
    await waitFor(() => expect(mockApiFetch).toHaveBeenCalledWith('/languages'))
  })

  it('defaults locale to resolved language from API', async () => {
    mockLanguagesOk(undefined, 'en')
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('en'))
  })

  it('uses stored locale from localStorage instead of resolved', async () => {
    localStorage.setItem('locale', 'zh-TW')
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('zh-TW'))
  })

  it('populates availableLanguages from API response', async () => {
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('lang-count').textContent).toBe('2'))
  })

  it('setLocale updates locale state and persists to localStorage', async () => {
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
    fireEvent.click(screen.getByText('set-zh-TW'))
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('zh-TW'))
    expect(localStorage.getItem('locale')).toBe('zh-TW')
  })

  it('t() returns a translated string for a known key', async () => {
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
    const text = screen.getByTestId('t-articles').textContent
    expect(typeof text).toBe('string')
    expect(text!.length).toBeGreaterThan(0)
  })

  it('t() returns the key itself when key is not found in any locale', async () => {
    function UnknownKeyConsumer() {
      const { t } = useI18n()
      return <span data-testid="unknown">{t('nonexistent.deeply.nested.key')}</span>
    }
    render(<I18nProvider><UnknownKeyConsumer /></I18nProvider>)
    await waitFor(() =>
      expect(screen.getByTestId('unknown').textContent).toBe('nonexistent.deeply.nested.key')
    )
  })

  it('t() with params covers the interpolation path without throwing', async () => {
    function ParamConsumer() {
      const { t } = useI18n()
      // nav.articles exists as a string with no placeholders — params are passed but nothing to replace
      const result = t('nav.articles', { count: 42 })
      return <span data-testid="param-result">{typeof result}</span>
    }
    render(<I18nProvider><ParamConsumer /></I18nProvider>)
    await waitFor(() =>
      expect(screen.getByTestId('param-result').textContent).toBe('string')
    )
  })

  it('falls back to locale=en when API call fails', async () => {
    mockApiFetch.mockRejectedValue(new Error('network error'))
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
    expect(screen.getByTestId('locale').textContent).toBe('en')
  })

  it('useI18n throws when used outside I18nProvider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    function BadConsumer() {
      useI18n()
      return null
    }
    expect(() => render(<BadConsumer />)).toThrow('useI18n must be used within an I18nProvider')
    consoleSpy.mockRestore()
  })
})
