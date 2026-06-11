'use client'
import { usePathname } from 'next/navigation'
import { NavBar } from '@/components/features/navigation/nav-bar'
import { ErrorBoundary } from '@/components/common/error-boundary'
import { FloatingChatbotWrapper } from '@/components/features/rag/FloatingChatbotWrapper'

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isStandalone = pathname.startsWith('/articles/')

  return (
    <ErrorBoundary>
      {!isStandalone && <NavBar />}
      <main className={isStandalone
        ? 'min-h-screen flex items-center justify-center p-6'
        : 'container mx-auto px-6 py-8 pt-24'
      }>
        {children}
      </main>
      <FloatingChatbotWrapper />
    </ErrorBoundary>
  )
}
