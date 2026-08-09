import TagsPageContent from './tags-page-content'
import { resolveSsrContext, fetchTagGroupsSSR } from '@/lib/server/ssr-fetch'

export default async function TagsPage() {
  const context = await resolveSsrContext()
  const initialGroups = await fetchTagGroupsSSR(context)

  return <TagsPageContent initialGroups={initialGroups ?? undefined} />
}
