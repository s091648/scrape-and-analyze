'use client'
import Link from 'next/link'
import { useSession, signOut } from 'next-auth/react'

export function NavBar() {
  const { data: session } = useSession()
  const isAdmin = (session?.user as any)?.role === 'admin'

  return (
    <nav className="border-b px-6 py-3 flex items-center gap-6">
      <Link href="/" className="font-semibold">Scrape Analyzer</Link>
      <Link href="/graph">Knowledge Graph</Link>
      {isAdmin && <Link href="/admin/scraper-settings">Scraper Settings</Link>}
      <div className="ml-auto">
        {session ? (
          <button onClick={() => signOut()}>Logout</button>
        ) : (
          <Link href="/login">Login</Link>
        )}
      </div>
    </nav>
  )
}