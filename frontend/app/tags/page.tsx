import TagsPageContent from './tags-page-content'
import { resolveSsrContext, fetchTagGroupsSSR } from '@/lib/server/ssr-fetch'

export default async function TagsPage() {
  const context = await resolveSsrContext()
  const result = await fetchTagGroupsSSR(context)

  return (
    <>
      <TagsPageContent initialGroups={result?.value} />
      {/* Debug aid (020-redis-caching-layer verification) — this fetch runs server-to-server, so
          the backend's X-Cache response header never reaches the browser; surfaced here instead so
          it's inspectable via view-source/DOM after a Lighthouse run. Safe to remove later. */}
      <span data-ssr-cache-status={result?.cacheStatus ?? 'NONE'} data-ssr-cache-namespace="tag_groups" hidden />
    </>
  )
}
