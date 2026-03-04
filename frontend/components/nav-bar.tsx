'use client'
import Link from 'next/link'
import { useSession, signOut } from 'next-auth/react'
import { Button } from '@/components/ui/button'
import { Rss } from 'lucide-react'

export function NavBar() {
  const { data: session } = useSession()
  const isAdmin = (session?.user as any)?.role === 'admin'

  return (
    <header className="fixed left-0 top-0 right-0 z-50 w-full border-b border-border bg-background">
      <nav className="container mx-auto px-6 h-16 flex items-center gap-12">
        <Link href="/" className="flex items-center gap-2 font-bold text-base shrink-0">
          <Rss className="h-4 w-4 text-primary" />
          Scrape Analyzer
        </Link>
        <div className="flex items-center gap-6 flex-1">
          <Link
            href="/"
            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors duration-200"
          >
            Articles
          </Link>
          <Link
            href="/graph"
            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors duration-200"
          >
            Knowledge Graph
          </Link>
          {isAdmin && (
            <>
              <Link
                href="/admin/scraper-settings"
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors duration-200"
              >
                Settings
              </Link>
              <Link
                href="/admin/users"
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors duration-200"
              >
                Users
              </Link>
            </>
          )}
        </div>
        <div className="ml-auto shrink-0">
          {session ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => signOut()}
              className="rounded-full h-8 px-4 text-sm font-medium"
            >
              Logout
            </Button>
          ) : (
            <Button
              asChild
              size="sm"
              className="rounded-full h-8 px-4 text-sm font-medium"
            >
              <Link href="/login">Login</Link>
            </Button>
          )}
        </div>
      </nav>
    </header>
  )
}
