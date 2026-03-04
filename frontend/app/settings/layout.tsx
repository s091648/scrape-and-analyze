'use client'
import Link from 'next/link'
import { usePathname, redirect } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { cn } from '@/lib/utils'

const profileItems = [
  { href: '/settings', label: 'Profile' },
]

const adminItems = [
  { href: '/admin/scraper-settings', label: 'Scraper Settings' },
  { href: '/admin/user-management', label: 'User Management' },
]

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { data: session, status } = useSession()

  if (status === 'unauthenticated') redirect('/login')

  const isAdmin = (session?.user as any)?.role === 'admin'

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
              {item.label}
            </Link>
          ))}

          {isAdmin && (
            <>
              <p className="px-3 pt-5 pb-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Admin
              </p>
              {adminItems.map(item => (
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
                  {item.label}
                </Link>
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
