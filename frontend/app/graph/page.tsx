import GraphPageContent from './graph-page-content'
import { resolveSsrContext, fetchGraphSSR } from '@/lib/server/ssr-fetch'

export default async function GraphPage() {
  const context = await resolveSsrContext()
  const result = await fetchGraphSSR(context)

  return (
    <>
      <GraphPageContent initialData={result?.value} />
      {/* Debug aid (020-redis-caching-layer verification) — this fetch runs server-to-server, so
          the backend's X-Cache response header never reaches the browser; surfaced here instead so
          it's inspectable via view-source/DOM after a Lighthouse run. Safe to remove later. */}
      <span data-ssr-cache-status={result?.cacheStatus ?? 'NONE'} data-ssr-cache-namespace="graph" hidden />
    </>
  )
}
