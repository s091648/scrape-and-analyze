'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import en from './locales/en.json'
import zhTW from './locales/zh-TW.json'

type Translations = typeof en

const translations: Record<string, Translations> = {
  en,
  'zh-TW': zhTW,
}

interface LanguageInfo {
  code: string
  name: string
  native_name: string
}

interface I18nContextType {
  locale: string
  setLocale: (locale: string) => void
  t: (key: string) => string
  availableLanguages: LanguageInfo[]
  resolvedLanguage: string
  isLoading: boolean
}

const I18nContext = createContext<I18nContextType | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState('en')
  const [availableLanguages, setAvailableLanguages] = useState<LanguageInfo[]>([
    { code: 'en', name: 'English', native_name: 'English' },
    { code: 'zh-TW', name: 'Traditional Chinese', native_name: '繁體中文' },
  ])
  const [resolvedLanguage, setResolvedLanguage] = useState('en')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Fetch available languages and resolved language from API
    fetch('/api/proxy/api/languages')
      .then(res => res.json())
      .then(data => {
        setAvailableLanguages(data.available || [])
        const resolved = data.resolved || 'en'
        setResolvedLanguage(resolved)
        // Use resolved language or fallback to stored preference or English
        const stored = localStorage.getItem('locale')
        setLocaleState(stored || resolved)
      })
      .catch(() => {
        // Fallback to English if API fails
        setLocaleState('en')
      })
      .finally(() => setIsLoading(false))
  }, [])

  const setLocale = (newLocale: string) => {
    setLocaleState(newLocale)
    localStorage.setItem('locale', newLocale)
  }

  const t = (key: string): string => {
    const keys = key.split('.')
    let value: any = translations[locale]

    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k]
      } else {
        // Fallback to English
        value = translations['en']
        for (const k2 of keys) {
          if (value && typeof value === 'object' && k2 in value) {
            value = value[k2]
          } else {
            return key // Return key if not found
          }
        }
        break
      }
    }

    return typeof value === 'string' ? value : key
  }

  return (
    <I18nContext.Provider value={{ locale, setLocale, t, availableLanguages, resolvedLanguage, isLoading }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider')
  }
  return context
}