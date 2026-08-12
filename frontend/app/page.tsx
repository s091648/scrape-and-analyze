import { Suspense } from 'react'
import { preload } from 'react-dom'
import HomePageContent from './home-page-content'
import { resolveSsrContext, fetchWeeklyReportSSR } from '@/lib/server/ssr-fetch'

export default async function Page() {
  // Home has no paywall — weekly-report-widget.tsx shows the latest report to every visitor
  // regardless of auth state (unlike /articles, /graph, /tags) — so anonymous visitors get a
  // guest credential rather than being skipped entirely. See SsrContext's doc comment.
  const context = await resolveSsrContext({ allowGuestCredential: true })
  const result = await fetchWeeklyReportSSR(context)

  // The cover image renders as a CSS background-image (knowledge of its URL isn't visible to
  // the browser's preload scanner the way an <img src> tag would be) — this resource hint tells
  // the browser to start fetching it immediately, in parallel with hydration, instead of only
  // once the client re-derives the same URL and applies the style.
  if (result?.value.cover_image_url) {
    preload(result.value.cover_image_url, { as: 'image', fetchPriority: 'high' })
  }

  return (
    <Suspense fallback={<div />}>
      <HomePageContent initialReport={result?.value} />
      {/* Debug aid (020-redis-caching-layer verification) — this fetch runs server-to-server, so
          the backend's X-Cache response header never reaches the browser; surfaced here instead so
          it's inspectable via view-source/DOM after a Lighthouse run. Safe to remove later. */}
      <span data-ssr-cache-status={result?.cacheStatus ?? 'NONE'} data-ssr-cache-namespace="weekly_reports" hidden />
    </Suspense>
  )
}
