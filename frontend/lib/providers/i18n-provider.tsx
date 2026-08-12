'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { apiFetch } from '@/lib/api/client'
import { useAuthToken } from './auth-token-provider'
import { setPreferenceCookie } from '@/lib/cookies/set-preference-cookie'
import { LOCALE_COOKIE_NAME } from '@/lib/cookies/constants'
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
  t: (key: string, params?: Record<string, string | number>) => string
  availableLanguages: LanguageInfo[]
  resolvedLanguage: string
  isLoading: boolean
}

const I18nContext = createContext<I18nContextType | null>(null)

interface I18nProviderProps {
  children: ReactNode
  /** Server-resolved locale (`lib/server/ssr-fetch.ts`'s `resolveVisitorTopicAndLocale`, called
   * from `app/layout.tsx`) — seeds `locale` so the very first render (server AND client
   * hydration) already shows translated text in the right language instead of always starting
   * 'en' and correcting after a client-side geo-IP/cookie fetch (021-ssr-public-pages). */
  initialLocale?: string
}

export function I18nProvider({ children, initialLocale }: I18nProviderProps) {
  const [locale, setLocaleState] = useState(initialLocale || 'en')
  const [availableLanguages, setAvailableLanguages] = useState<LanguageInfo[]>([
    { code: 'en', name: 'English', native_name: 'English' },
    { code: 'zh-TW', name: 'Traditional Chinese', native_name: '繁體中文' },
  ])
  const [resolvedLanguage, setResolvedLanguage] = useState(initialLocale || 'en')
  const [isLoading, setIsLoading] = useState(!initialLocale)
  // 018-public-api-auth: /languages now requires a token — wait for
  // AuthTokenProvider to resolve one (real session or guest) before calling,
  // so this doesn't race the guest-token bootstrap on a fresh anonymous visit.
  const { token, isLoading: authLoading } = useAuthToken()

  useEffect(() => {
    if (authLoading || !token) return

    apiFetch('/languages', {}, undefined, { silent: true })
      .then(res => res.json())
      .then(data => {
        setAvailableLanguages(data.available || [])
        const resolved = data.resolved || 'en'
        setResolvedLanguage(resolved)
        const stored = localStorage.getItem('locale')
        if (!stored) {
          // Backfills the cookie for a true first-ever visitor, so their *next* visit's SSR
          // render (021-ssr-public-pages) already knows their geo-resolved language instead of
          // re-resolving from scratch — localStorage semantics here are otherwise unchanged.
          setPreferenceCookie(LOCALE_COOKIE_NAME, resolved)
        }
        setLocaleState(stored || resolved)
      })
      .catch(() => {
        setLocaleState('en')
      })
      .finally(() => setIsLoading(false))
  }, [authLoading, token])

  const setLocale = (newLocale: string) => {
    setLocaleState(newLocale)
    localStorage.setItem('locale', newLocale)
    setPreferenceCookie(LOCALE_COOKIE_NAME, newLocale)
  }

  const t = (key: string, params?: Record<string, string | number>): string => {
    const keys = key.split('.')
    let value: any = translations[locale]

    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k]
      } else {
        value = translations['en']
        for (const k2 of keys) {
          if (value && typeof value === 'object' && k2 in value) {
            value = value[k2]
          } else {
            return key
          }
        }
        break
      }
    }

    if (typeof value !== 'string') return key
    if (params) {
      return value.replace(/\{(\w+)\}/g, (_, k) => params[k] != null ? String(params[k]) : `{${k}}`)
    }
    return value
  }

  return (
    <I18nContext.Provider value={{ locale, setLocale, t, availableLanguages, resolvedLanguage, isLoading }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n must be used within an I18nProvider')
  return context
}
