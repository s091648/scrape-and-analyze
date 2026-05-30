import type { Metadata } from 'next'
import { Rethink_Sans } from 'next/font/google'
import './globals.css'
import { AppProviders } from '@/lib/providers'
import { LayoutShell } from './layout-shell'

const rethinkSans = Rethink_Sans({ subsets: ['latin'], variable: '--font-rethink' })

export const metadata: Metadata = { title: 'Scrape Analyzer' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${rethinkSans.variable} font-sans`}>
        <AppProviders>
          <LayoutShell>{children}</LayoutShell>
        </AppProviders>
      </body>
    </html>
  )
}