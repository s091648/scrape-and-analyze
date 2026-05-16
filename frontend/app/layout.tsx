import type { Metadata } from 'next'
import { Rethink_Sans } from 'next/font/google'
import './globals.css'
import { ErrorBoundary } from '@/components/error-boundary'
import { NavBar } from '@/components/nav-bar'
import SessionProviderWrapper from '@/components/session-provider'
import { TopicProvider } from '@/contexts/topic-context'
import { I18nProvider } from '@/i18n'

const rethinkSans = Rethink_Sans({ subsets: ['latin'], variable: '--font-rethink' })

export const metadata: Metadata = { title: 'Scrape Analyzer' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${rethinkSans.variable} font-sans`}>
        <SessionProviderWrapper>
          <TopicProvider>
            <I18nProvider>
              <ErrorBoundary>
                <NavBar />
                <main className="container mx-auto px-6 py-8 pt-24">{children}</main>
              </ErrorBoundary>
            </I18nProvider>
          </TopicProvider>
        </SessionProviderWrapper>
      </body>
    </html>
  )
}