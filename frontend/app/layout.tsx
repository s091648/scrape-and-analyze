import type { Metadata } from 'next'
import { Rethink_Sans } from 'next/font/google'
import './globals.css'
import '@s091648/chatbot-plugin-ui/dist/style.css'
import { AppProviders } from '@/lib/providers'
import { LayoutShell } from './layout-shell'
import { Toaster } from 'sonner'

const rethinkSans = Rethink_Sans({ subsets: ['latin'], variable: '--font-rethink' })

export const metadata: Metadata = { title: 'Article Analyzer' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${rethinkSans.variable} font-sans`}>
        <AppProviders>
          <LayoutShell>{children}</LayoutShell>
          <Toaster richColors position="bottom-right" />
        </AppProviders>
      </body>
    </html>
  )
}