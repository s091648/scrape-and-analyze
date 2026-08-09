import GraphPageContent from './graph-page-content'
import { resolveSsrContext, fetchGraphSSR } from '@/lib/server/ssr-fetch'

export default async function GraphPage() {
  const context = await resolveSsrContext()
  const initialData = await fetchGraphSSR(context)

  return <GraphPageContent initialData={initialData ?? undefined} />
}
