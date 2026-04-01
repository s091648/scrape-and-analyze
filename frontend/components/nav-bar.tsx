'use client'
import Link from 'next/link'
import { useSession, signOut } from 'next-auth/react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Rss, Settings } from 'lucide-react'
import { apiFetch } from '@/lib/api-fetch'
import { Skeleton } from '@/components/ui/skeleton'

function initials(name: string | null | undefined): string {
  if (!name) return '?'
  return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
}

export function NavBar() {
  const { data: session } = useSession()
  const userName = session?.user?.name ?? (session?.user as any)?.username ?? session?.user?.email ?? ''
  const [userIcon, setUserIcon] = useState<string | null>(null)
  const [iconLoading, setIconLoading] = useState(false)
  const token = (session as any)?.accessToken

  useEffect(() => {
    if (!token) { setUserIcon(null); return }
    setIconLoading(true)
    apiFetch('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(profile => setUserIcon(profile?.icon ?? null))
      .finally(() => setIconLoading(false))
  }, [token])

  return (
    <header className="fixed left-0 top-0 right-0 z-50 w-full border-b border-border bg-background">
      <nav className="container mx-auto px-6 h-16 flex items-center gap-12">
        <Link href="/" className="flex items-center gap-2 font-bold text-base shrink-0">
          <Rss className="h-4 w-4 text-primary" />
          Scrape Analyzer
        </Link>

        {/* Left nav */}
        <div className="flex items-center gap-6">
          <Link href="/" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors duration-200">
            Articles
          </Link>
          <Link href="/graph" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors duration-200">
            Knowledge Graph
          </Link>
        </div>

        {/* Right nav */}
        <div className="ml-auto flex items-center gap-4 shrink-0">
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
                Logout
              </Button>
            </>
          ) : (
            <Button asChild size="sm" className="rounded-full h-8 px-4 text-sm font-medium">
              <Link href="/login">Login</Link>
            </Button>
          )}
        </div>
      </nav>
    </header>
  )
}
