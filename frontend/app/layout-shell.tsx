'use client'
import { usePathname } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { NavBar } from '@/components/features/navigation/nav-bar'
import { ErrorBoundary } from '@/components/common/error-boundary'
import { FloatingChatbotWrapper } from '@/components/features/chat/FloatingChatbotWrapper'

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { data: session, status } = useSession()
  const isStandalone = pathname.startsWith('/articles/')
  const isChatPath = ['/articles', '/graph', '/tags'].includes(pathname)
  // Remount the chatbot when the logged-in user changes so memory/localStorage
  // from a previous session is never visible to the next user.
  const chatKey = status === 'loading' ? 'loading' : ((session?.user as any)?.id ?? 'guest')

  return (
    <ErrorBoundary>
      {!isStandalone && <NavBar />}
      <main className={isStandalone
        ? 'min-h-screen flex items-center justify-center p-6'
        : 'container mx-auto px-6 py-8 pt-24'
      }>
        {children}
      </main>
      {isChatPath && <FloatingChatbotWrapper key={chatKey} />}
    </ErrorBoundary>
  )
}
