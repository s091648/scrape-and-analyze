'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useSession, signOut } from 'next-auth/react'
import { useEffect, useState, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Rss, Settings, ChevronDown, Globe } from 'lucide-react'
import { fetchMe } from '@/lib/api/auth'
import { Skeleton } from '@/components/ui/skeleton'
import { useTopic } from '@/lib/providers'
import { useI18n } from '@/lib/providers'

function initials(name: string | null | undefined): string {
  if (!name) return '?'
  return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
}

export function NavBar() {
  const { data: session } = useSession()
  const userName = session?.user?.name ?? (session?.user as any)?.username ?? session?.user?.email ?? ''
  const [userIcon, setUserIcon] = useState<string | null>(null)
  const [iconLoading, setIconLoading] = useState(false)
  const [langDropdownOpen, setLangDropdownOpen] = useState(false)
  const langDropdownRef = useRef<HTMLDivElement>(null)
  const token = (session as any)?.accessToken
  const { topics, selectedTopic, setSelectedTopicId, isLoading: topicsLoading } = useTopic()
  const { locale, setLocale, availableLanguages, t, isLoading: i18nLoading } = useI18n()

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target as Node)) {
        setLangDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (!token) { setUserIcon(null); return }
    setIconLoading(true)
    fetchMe(token).then(profile => setUserIcon(profile?.icon ?? null))
      .finally(() => setIconLoading(false))
  }, [token])

  const pathname = usePathname()
  const currentLang = availableLanguages.find(l => l.code === locale)
  const topicParam = selectedTopic ? `?topic=${selectedTopic.id}` : ''

  return (
    <header className="fixed left-0 top-0 right-0 z-50 w-full border-b border-border bg-background">
      <nav className="container mx-auto px-6 h-16 flex items-center gap-12 relative">
        <Link href="/" className="flex items-center gap-2 font-bold text-base shrink-0">
          <Rss className="h-4 w-4 text-primary" />
          Scrape Analyzer
        </Link>

        {/* Topic dropdown */}
        <div className="relative group">
          <button
            type="button"
            className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg border border-border bg-background hover:bg-muted transition-colors"
          >
            {topicsLoading ? (
              <Skeleton className="h-4 w-20" />
            ) : (
              <>
                {selectedTopic?.color_hex && (
                  <span
                    className="inline-block h-2 w-2 rounded-full shrink-0"
                    style={{ backgroundColor: selectedTopic.color_hex }}
                  />
                )}
                <span className="max-w-[120px] truncate">
                  {selectedTopic?.display_name ?? 'Select topic'}
                </span>
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              </>
            )}
          </button>
          {!topicsLoading && topics.length > 0 && (
            <div className="absolute left-0 top-full mt-1 w-48 rounded-lg border border-border bg-background shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
              {topics.map(t => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSelectedTopicId(t.id)}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors first:rounded-t-lg last:rounded-b-lg ${
                    t.id === selectedTopic?.id ? 'font-semibold' : ''
                  }`}
                >
                  {t.color_hex && (
                    <span
                      className="inline-block h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: t.color_hex }}
                    />
                  )}
                  {t.display_name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Left nav */}
        <div className="flex items-center gap-1">
          <Link
            href={`/${topicParam}`}
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors duration-200 ${
              pathname === '/'
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            {t('nav.articles')}
          </Link>
          <Link
            href={`/graph${topicParam}`}
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors duration-200 ${
              pathname === '/graph'
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            {t('nav.knowledgeGraph')}
          </Link>
          <Link
            href={`/tags${topicParam}`}
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors duration-200 ${
              pathname === '/tags'
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            {t('tags.title')}
          </Link>
        </div>

        {/* Env indicator — only shown in non-production environments */}
        {process.env.APP_ENV !== 'production' && (
          <span className="absolute left-1/2 -translate-x-1/2 text-xs font-semibold font-mono text-red-500 select-none pointer-events-none">
            {process.env.APP_ENV}
          </span>
        )}

        {/* Right nav */}
        <div className="ml-auto flex items-center gap-4 shrink-0">
          {/* Language dropdown */}
          <div className="relative" ref={langDropdownRef}>
            <button
              type="button"
              onClick={() => setLangDropdownOpen(!langDropdownOpen)}
              className="flex items-center gap-1.5 text-sm font-medium px-2 py-1.5 rounded-lg border border-border bg-background hover:bg-muted transition-colors"
            >
              <Globe className="h-4 w-4 text-muted-foreground" />
              <span>{i18nLoading ? '...' : currentLang?.native_name || locale}</span>
            </button>
            {langDropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-40 rounded-lg border border-border bg-background shadow-lg z-50">
                {availableLanguages.map(lang => (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => {
                      setLocale(lang.code)
                      setLangDropdownOpen(false)
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-muted transition-colors first:rounded-t-lg last:rounded-b-lg ${
                      lang.code === locale ? 'font-semibold bg-muted/50' : ''
                    }`}
                  >
                    <span>{lang.native_name}</span>
                    {lang.code === locale && <span>✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          {session && (
            <Link href="/settings" className="text-muted-foreground hover:text-foreground transition-colors duration-200">
              <Settings size={20} />
            </Link>
          )}

          {session ? (
            <>
              <div className="flex items-center gap-2.5">
                {iconLoading ? (
                  <Skeleton className="h-7 w-7 rounded-full" />
                ) : userIcon ? (
                  <img src={userIcon} className="h-7 w-7 rounded-full object-cover" alt="" />
                ) : (
                  <div className="h-7 w-7 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-semibold select-none">
                    {initials(userName)}
                  </div>
                )}
                <span className="text-sm font-medium max-w-[120px] truncate">{userName}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => signOut()}
                className="rounded-full h-8 px-4 text-sm font-medium"
              >
                {t('nav.logout')}
              </Button>
            </>
          ) : (
            <Button asChild size="sm" className="rounded-full h-8 px-4 text-sm font-medium">
              <Link href="/login">{t('nav.login')}</Link>
            </Button>
          )}
        </div>
      </nav>
    </header>
  )
}
