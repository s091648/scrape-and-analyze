import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { ErrorBoundary } from '@/components/error-boundary'
import { NavBar } from '@/components/nav-bar'
import SessionProviderWrapper from '@/components/session-provider'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = { title: 'Scrape Analyzer' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <SessionProviderWrapper>
          <ErrorBoundary>
            <NavBar />
            <main className="container mx-auto px-4 py-6">{children}</main>
          </ErrorBoundary>
        </SessionProviderWrapper>
      </body>
    </html>
  )
}