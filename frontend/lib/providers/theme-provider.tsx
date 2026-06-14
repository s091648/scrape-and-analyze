'use client'
import { createContext, useContext, useEffect, useState, useCallback } from 'react'

type ThemeMode = 'light' | 'dark' | 'auto'
type ResolvedTheme = 'light' | 'dark'

interface ThemeContextValue {
  mode: ThemeMode
  theme: ResolvedTheme
  setMode: (mode: ThemeMode) => void
  cycleMode: () => void
}

const ThemeContext = createContext<ThemeContextValue>({
  mode: 'auto',
  theme: 'light',
  setMode: () => {},
  cycleMode: () => {},
})

const STORAGE_KEY = 'app-theme-mode'
const CYCLE: ThemeMode[] = ['light', 'dark', 'auto']

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function resolveTheme(mode: ThemeMode): ResolvedTheme {
  return mode === 'auto' ? getSystemTheme() : mode
}

function applyTheme(resolved: ResolvedTheme) {
  document.documentElement.classList.toggle('dark', resolved === 'dark')
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>('auto')
  const [theme, setTheme] = useState<ResolvedTheme>('light')

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as ThemeMode | null
    const initial: ThemeMode = saved && CYCLE.includes(saved) ? saved : 'auto'
    const resolved = resolveTheme(initial)
    setModeState(initial)
    setTheme(resolved)
    applyTheme(resolved)
  }, [])

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => {
      if (mode === 'auto') {
        const resolved = getSystemTheme()
        setTheme(resolved)
        applyTheme(resolved)
      }
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [mode])

  const setMode = useCallback((newMode: ThemeMode) => {
    const resolved = resolveTheme(newMode)
    setModeState(newMode)
    setTheme(resolved)
    localStorage.setItem(STORAGE_KEY, newMode)
    applyTheme(resolved)
  }, [])

  const cycleMode = useCallback(() => {
    setMode(CYCLE[(CYCLE.indexOf(mode) + 1) % CYCLE.length])
  }, [mode, setMode])

  return (
    <ThemeContext.Provider value={{ mode, theme, setMode, cycleMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
