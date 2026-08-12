import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { I18nProvider, useI18n } from '@/lib/providers/i18n-provider'
import { LOCALE_COOKIE_NAME } from '@/lib/cookies/constants'

const { mockApiFetch } = vi.hoisted(() => ({ mockApiFetch: vi.fn() }))
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

// 021-ssr-public-pages: setLocale and the first-ever geo-IP-resolution effect also write a
// preference cookie (frontend/lib/cookies/set-preference-cookie.ts) alongside localStorage —
// spy on it directly so a wrong-name/wrong-value write fails loudly instead of silently no-oping.
const { mockSetPreferenceCookie } = vi.hoisted(() => ({ mockSetPreferenceCookie: vi.fn() }))
vi.mock('@/lib/cookies/set-preference-cookie', () => ({ setPreferenceCookie: mockSetPreferenceCookie }))
// 018-public-api-auth: I18nProvider now waits for a resolved auth token
// (real session or guest) before calling /languages.
vi.mock('@/lib/providers/auth-token-provider', () => ({
  useAuthToken: () => ({ token: 'test-token', isLoading: false }),
}))

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

function renderProviderWithInitialLocale(initialLocale: string) {
  return render(<I18nProvider initialLocale={initialLocale}><TestConsumer /></I18nProvider>)
}

describe('I18nProvider', () => {
  it('starts loading and resolves to ready', async () => {
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
  })

  it('calls apiFetch to resolve available languages on mount', async () => {
    renderProvider()
    await waitFor(() =>
      expect(mockApiFetch).toHaveBeenCalledWith('/languages', {}, undefined, { silent: true })
    )
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
    mockSetPreferenceCookie.mockClear() // drop any on-mount backfill call, isolate the click
    fireEvent.click(screen.getByText('set-zh-TW'))
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('zh-TW'))
    expect(localStorage.getItem('locale')).toBe('zh-TW')
    expect(mockSetPreferenceCookie).toHaveBeenCalledWith(LOCALE_COOKIE_NAME, 'zh-TW')
  })

  it('backfills the preference cookie for a first-time visitor (no prior localStorage value)', async () => {
    mockLanguagesOk(undefined, 'zh-TW')
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('zh-TW'))
    expect(mockSetPreferenceCookie).toHaveBeenCalledWith(LOCALE_COOKIE_NAME, 'zh-TW')
  })

  it('does not backfill the cookie when a localStorage value already existed', async () => {
    localStorage.setItem('locale', 'zh-TW')
    mockLanguagesOk(undefined, 'en') // geo-resolved differs, but stored value wins and is not a "first-ever" visit
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('locale').textContent).toBe('zh-TW'))
    expect(mockSetPreferenceCookie).not.toHaveBeenCalled()
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

  // 021-ssr-public-pages: app/layout.tsx passes the server-resolved locale (shared, via
  // resolveVisitorTopicAndLocale's cache(), with whatever a page's own SSR fetch used) so the
  // very first render — server AND client hydration — already shows translated text instead of
  // always starting 'en'.
  it('seeds locale from initialLocale immediately, before the /languages call resolves', async () => {
    renderProviderWithInitialLocale('zh-TW')
    expect(screen.getByTestId('locale').textContent).toBe('zh-TW')
    expect(screen.getByTestId('loading').textContent).toBe('ready')
    // Let the background /languages effect settle so it doesn't leak into the next test.
    await waitFor(() => expect(mockApiFetch).toHaveBeenCalled())
  })

  it('still resolves availableLanguages/isLoading normally once seeded', async () => {
    renderProviderWithInitialLocale('en')
    await waitFor(() => expect(screen.getByTestId('lang-count').textContent).toBe('2'))
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
