'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

const sidebarItems = [
  { href: '/admin/scraper-settings', label: 'Scraper Settings' },
  { href: '/admin/user-management', label: 'User Management' },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">
      <aside className="w-56 shrink-0 border-r border-border pt-8 px-3">
        <p className="px-3 mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Admin</p>
        <nav className="space-y-0.5">
          {sidebarItems.map(item => (
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
        </nav>
      </aside>

      <main className="flex-1 px-10 py-8 overflow-auto">
        {children}
      </main>
    </div>
  )
}
