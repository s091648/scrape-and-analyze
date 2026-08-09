import { Suspense } from 'react'
import { preload } from 'react-dom'
import HomePageContent from './home-page-content'
import { resolveSsrContext, fetchWeeklyReportSSR } from '@/lib/server/ssr-fetch'

export default async function Page() {
  // Home has no paywall — weekly-report-widget.tsx shows the latest report to every visitor
  // regardless of auth state (unlike /articles, /graph, /tags) — so anonymous visitors get a
  // guest credential rather than being skipped entirely. See SsrContext's doc comment.
  const context = await resolveSsrContext({ allowGuestCredential: true })
  const initialReport = await fetchWeeklyReportSSR(context)

  // The cover image renders as a CSS background-image (knowledge of its URL isn't visible to
  // the browser's preload scanner the way an <img src> tag would be) — this resource hint tells
  // the browser to start fetching it immediately, in parallel with hydration, instead of only
  // once the client re-derives the same URL and applies the style.
  if (initialReport?.cover_image_url) {
    preload(initialReport.cover_image_url, { as: 'image', fetchPriority: 'high' })
  }

  return (
    <Suspense fallback={<div />}>
      <HomePageContent initialReport={initialReport} />
    </Suspense>
  )
}
