import type { Metadata } from 'next'
import { Rethink_Sans } from 'next/font/google'
import './globals.css'
import { ErrorBoundary } from '@/components/common/error-boundary'
import { NavBar } from '@/components/features/navigation/nav-bar'
import { AppProviders } from '@/lib/providers'

const rethinkSans = Rethink_Sans({ subsets: ['latin'], variable: '--font-rethink' })

export const metadata: Metadata = { title: 'Scrape Analyzer' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${rethinkSans.variable} font-sans`}>
        <AppProviders>
          <ErrorBoundary>
            <NavBar />
            <main className="container mx-auto px-6 py-8 pt-24">{children}</main>
          </ErrorBoundary>
        </AppProviders>
      </body>
    </html>
  )
}