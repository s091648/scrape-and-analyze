import type { Metadata } from 'next'
import { Rethink_Sans } from 'next/font/google'
import './globals.css'
import '@s091648/chatbot-plugin-ui/dist/style.css'
import { AppProviders } from '@/lib/providers'
import { LayoutShell } from './layout-shell'
import { Toaster } from 'sonner'
import { resolveVisitorTopicAndLocale } from '@/lib/server/ssr-fetch'

const rethinkSans = Rethink_Sans({ subsets: ['latin'], variable: '--font-rethink' })

export const metadata: Metadata = {
  title: 'Article Analyzer',
  description: 'AI-powered analysis and tagging of the latest AI/ML research and tech articles, with topic-based browsing, a knowledge graph, and weekly summary reports.',
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Seeds TopicProvider/I18nProvider so their first render (server AND client hydration) already
  // reflects the visitor's real topic/language instead of starting null/'en' and only correcting
  // after a client-side re-fetch — see specs/021-ssr-public-pages research.md's cache()-sharing
  // decision. Every page under this layout that also calls resolveSsrContext() (the 4 converted
  // routes) shares this exact same resolution within the request — no duplicate round-trip.
  const { topicId, locale } = await resolveVisitorTopicAndLocale()

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${rethinkSans.variable} font-sans`}>
        <AppProviders initialTopicId={topicId} initialLocale={locale}>
          <LayoutShell>{children}</LayoutShell>
          <Toaster richColors position="bottom-right" />
        </AppProviders>
      </body>
    </html>
  )
}
