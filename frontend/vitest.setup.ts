import '@testing-library/jest-dom'
import { vi } from 'vitest'

// jsdom does not implement ResizeObserver; provide a no-op stub
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// jsdom does not implement scrollIntoView; provide a no-op stub
Element.prototype.scrollIntoView = vi.fn()

// Global mock so components that call useI18n() don't require a real I18nProvider in tests.
vi.mock('@/i18n', () => ({
  useI18n: () => ({
    locale: 'en',
    setLocale: () => {},
    t: (key: string) => key,
    availableLanguages: [],
    resolvedLanguage: 'en',
    isLoading: false,
  }),
  I18nProvider: ({ children }: { children: React.ReactNode }) => children,
}))