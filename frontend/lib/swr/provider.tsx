'use client'
import { SWRConfig } from 'swr'

/** App-wide SWR cache boundary. No custom `provider`/`cache` option — SWR's default is a plain
 * in-memory Map scoped to this page load, which matches every existing hand-rolled cache in this
 * codebase (ssr-fetch.ts's guest-token cache): cleared on reload, never persisted to
 * localStorage/sessionStorage. Individual hooks (see `hooks/use-*-feed.ts`) set their own
 * `fallbackData`/`revalidateOnMount` per call — nothing global to configure here beyond the
 * cache boundary itself. */
export function SWRProvider({ children }: { children: React.ReactNode }) {
  return <SWRConfig value={{}}>{children}</SWRConfig>
}
