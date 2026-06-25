import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import React from 'react'
import { ThemeProvider, useTheme } from '@/lib/providers/theme-provider'

// ── matchMedia helpers ────────────────────────────────────────────────────────

let _systemDark = false
let _changeListeners: Array<(e: { matches: boolean }) => void> = []

function setupMatchMedia(dark: boolean) {
  _systemDark = dark
  _changeListeners = []
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)' ? _systemDark : false,
      addEventListener: vi.fn((event: string, fn: any) => {
        if (event === 'change') _changeListeners.push(fn)
      }),
      removeEventListener: vi.fn((event: string, fn: any) => {
        if (event === 'change') {
          const idx = _changeListeners.indexOf(fn)
          if (idx !== -1) _changeListeners.splice(idx, 1)
        }
      }),
      dispatchEvent: vi.fn(),
    })),
  })
}

function fireSystemChange(dark: boolean) {
  _changeListeners.forEach(fn => fn({ matches: dark }))
}

// ── Consumer helper ───────────────────────────────────────────────────────────

function Consumer() {
  const { mode, theme, cycleMode, setMode } = useTheme()
  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="theme">{theme}</span>
      <button data-testid="cycle" onClick={cycleMode}>cycle</button>
      <button data-testid="set-light" onClick={() => setMode('light')}>light</button>
      <button data-testid="set-dark" onClick={() => setMode('dark')}>dark</button>
      <button data-testid="set-auto" onClick={() => setMode('auto')}>auto</button>
    </div>
  )
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
  setupMatchMedia(false)
})

describe('ThemeProvider — initial state', () => {
  it('defaults to auto mode when localStorage is empty', () => {
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    expect(screen.getByTestId('mode').textContent).toBe('auto')
  })

  it('reads saved mode from localStorage on mount', () => {
    localStorage.setItem('app-theme-mode', 'dark')
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    expect(screen.getByTestId('mode').textContent).toBe('dark')
  })

  it('falls back to auto for invalid localStorage value', () => {
    localStorage.setItem('app-theme-mode', 'invalid-value')
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    expect(screen.getByTestId('mode').textContent).toBe('auto')
  })

  it('theme is always "light" or "dark" — never "auto"', () => {
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    expect(['light', 'dark']).toContain(screen.getByTestId('theme').textContent)
  })
})

describe('ThemeProvider — cycleMode', () => {
  it('cycles light → dark → auto → light', () => {
    localStorage.setItem('app-theme-mode', 'light')
    render(<ThemeProvider><Consumer /></ThemeProvider>)

    expect(screen.getByTestId('mode').textContent).toBe('light')
    fireEvent.click(screen.getByTestId('cycle'))
    expect(screen.getByTestId('mode').textContent).toBe('dark')
    fireEvent.click(screen.getByTestId('cycle'))
    expect(screen.getByTestId('mode').textContent).toBe('auto')
    fireEvent.click(screen.getByTestId('cycle'))
    expect(screen.getByTestId('mode').textContent).toBe('light')
  })

  it('starts cycling from current saved mode', () => {
    localStorage.setItem('app-theme-mode', 'dark')
    render(<ThemeProvider><Consumer /></ThemeProvider>)

    fireEvent.click(screen.getByTestId('cycle'))
    expect(screen.getByTestId('mode').textContent).toBe('auto')
  })
})

describe('ThemeProvider — setMode', () => {
  it('setMode("dark") adds .dark class to <html>', () => {
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    fireEvent.click(screen.getByTestId('set-dark'))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('setMode("light") removes .dark class from <html>', () => {
    document.documentElement.classList.add('dark')
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    fireEvent.click(screen.getByTestId('set-light'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('setMode persists to localStorage', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem')
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    fireEvent.click(screen.getByTestId('set-dark'))
    expect(spy).toHaveBeenCalledWith('app-theme-mode', 'dark')
    spy.mockRestore()
  })

  it('setMode("dark") resolves theme to "dark"', () => {
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    fireEvent.click(screen.getByTestId('set-dark'))
    expect(screen.getByTestId('theme').textContent).toBe('dark')
  })

  it('setMode("light") resolves theme to "light"', () => {
    localStorage.setItem('app-theme-mode', 'dark')
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    fireEvent.click(screen.getByTestId('set-light'))
    expect(screen.getByTestId('theme').textContent).toBe('light')
  })
})

describe('ThemeProvider — on mount with saved dark', () => {
  it('adds .dark class immediately when localStorage has "dark"', () => {
    localStorage.setItem('app-theme-mode', 'dark')
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})

describe('ThemeProvider — auto mode + system preference', () => {
  it('auto + system dark → adds .dark class and resolves theme to "dark"', () => {
    setupMatchMedia(true)
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(screen.getByTestId('theme').textContent).toBe('dark')
  })

  it('auto + system light → no .dark class and resolves theme to "light"', () => {
    setupMatchMedia(false)
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(screen.getByTestId('theme').textContent).toBe('light')
  })

  it('auto mode reacts immediately when system switches to dark', () => {
    setupMatchMedia(false)
    render(<ThemeProvider><Consumer /></ThemeProvider>)
    expect(document.documentElement.classList.contains('dark')).toBe(false)

    act(() => fireSystemChange(true))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(screen.getByTestId('theme').textContent).toBe('dark')
  })

  it('auto mode reacts immediately when system switches back to light', () => {
    setupMatchMedia(true)
    render(<ThemeProvider><Consumer /></ThemeProvider>)

    act(() => fireSystemChange(false))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(screen.getByTestId('theme').textContent).toBe('light')
  })

  it('explicit dark mode does NOT react to system theme change', () => {
    localStorage.setItem('app-theme-mode', 'dark')
    setupMatchMedia(true)
    render(<ThemeProvider><Consumer /></ThemeProvider>)

    // Switch to light explicitly
    fireEvent.click(screen.getByTestId('set-light'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)

    // System fires dark — should be ignored because mode is "light"
    act(() => fireSystemChange(true))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('switching from auto to dark stops reacting to system', () => {
    setupMatchMedia(false)
    render(<ThemeProvider><Consumer /></ThemeProvider>)

    // Enter dark mode explicitly
    fireEvent.click(screen.getByTestId('set-dark'))
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    // System says light → no effect because mode is "dark"
    act(() => fireSystemChange(false))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})

describe('useTheme — outside provider', () => {
  it('returns safe default values when no ThemeProvider wraps', () => {
    function Bare() {
      const { mode, theme } = useTheme()
      return <span data-testid="val">{mode}/{theme}</span>
    }
    render(<Bare />)
    expect(screen.getByTestId('val').textContent).toBe('auto/light')
  })
})
