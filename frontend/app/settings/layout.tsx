'use client'
import Link from 'next/link'
import { usePathname, redirect } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { cn } from '@/lib/utils'
import { useTopic } from '@/lib/providers/topic-provider'
import { useI18n } from '@/i18n'

const profileItems = [
  { href: '/settings', labelKey: 'settings.profile' },
]

const adminItems = [
  { href: '/admin/topics', labelKey: 'admin.topics' },
  { href: '/admin/scraper-settings', labelKey: 'admin.scraperSettings' },
  { href: '/admin/user-management', labelKey: 'admin.userManagement' },
  { href: '/admin/monitoring', labelKey: 'admin.monitoring' },
]

export function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { data: session, status } = useSession()
  const { t } = useI18n()

  if (status === 'unauthenticated') redirect('/login')

  const isAdmin = (session?.user as any)?.role === 'admin'
  const { selectedTopic } = useTopic()

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      <aside className="w-56 shrink-0 border-r border-border pt-8 px-3">
        <nav className="space-y-0.5">
          {profileItems.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
                pathname === item.href
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              )}
            >
              {t(item.labelKey)}
            </Link>
          ))}

          {isAdmin && (
            <>
              <p className="px-3 pt-5 pb-1 text-xs font-bold text-black uppercase tracking-wider">
                Admin
              </p>
              {adminItems.map(item => (
                <div key={item.href} className="relative">
                  {item.href === '/admin/scraper-settings' && selectedTopic?.color_hex && (
                    <span
                      className="absolute -left-3 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full"
                      style={{ backgroundColor: selectedTopic.color_hex }}
                    />
                  )}
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'relative flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
                      pathname === item.href
                        ? 'bg-muted text-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                    )}
                  >
                    {t(item.labelKey)}
                  </Link>
                </div>
              ))}
            </>
          )}
        </nav>
      </aside>

      <main className="flex-1 px-10 py-8 overflow-auto">
        {children}
      </main>
    </div>
  )
}

export default SettingsLayout
