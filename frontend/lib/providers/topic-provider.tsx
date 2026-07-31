'use client'
import { createContext, useContext, useEffect, useState, ReactNode, Suspense } from 'react'
import { useRouter, useSearchParams, usePathname } from 'next/navigation'
import { fetchTopics } from '@/lib/api/topics'
import { useAuthToken } from './auth-token-provider'

export type TagMode = 'unsupervised' | 'semi_supervised' | 'supervised'

export interface Topic {
  id: string
  name: string
  display_name: string
  color_hex: string | null
  sort_order: number | null
  tag_mode: TagMode
}

interface TopicContextValue {
  topics: Topic[]
  selectedTopicId: string | null
  selectedTopic: Topic | null
  setSelectedTopicId: (id: string) => void
  refresh: () => Promise<void>
  isLoading: boolean
}

const TopicContext = createContext<TopicContextValue>({
  topics: [],
  selectedTopicId: null,
  selectedTopic: null,
  setSelectedTopicId: () => {},
  refresh: async () => {},
  isLoading: true,
})

const STORAGE_KEY = 'selectedTopicId'

// Inner component — must be wrapped in <Suspense> (Next.js App Router requirement for useSearchParams in layouts)
function TopicUrlSync({
  topics,
  selectedTopicId,
  initialized,
  onTopicFromUrl,
}: {
  topics: Topic[]
  selectedTopicId: string | null
  initialized: boolean
  onTopicFromUrl: (id: string) => void
}) {
  const searchParams = useSearchParams()
  const router = useRouter()
  const pathname = usePathname()

  // URL → state: run once topics are loaded, honour ?topic= for sharing/bookmarking
  useEffect(() => {
    if (!initialized || topics.length === 0) return
    const urlId = searchParams.get('topic')
    if (urlId && topics.find(t => t.id === urlId) && urlId !== selectedTopicId) {
      onTopicFromUrl(urlId)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialized, topics.length])

  // State → URL: keep URL in sync with current topic, preserving other params (e.g. `week`)
  useEffect(() => {
    if (!selectedTopicId) return
    // /login and /register aren't topic-scoped, and — now that /topics succeeds
    // pre-auth for guests (it used to 401 silently before token-gating) — this
    // effect can fire while still on /login, e.g. right as a "Continue as
    // Guest" click is navigating away via router.push('/'). A replace() here
    // using this render's (possibly stale, pre-navigation) `pathname` would
    // race that push and strand the user back on /login?topic=... .
    if (pathname === '/login' || pathname === '/register') return
    if (searchParams.get('topic') === selectedTopicId) return
    const params = new URLSearchParams(searchParams.toString())
    params.set('topic', selectedTopicId)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  // searchParams is a dependency (not just selectedTopicId/pathname) so this
  // always writes `topic` on top of the current URL rather than a stale
  // snapshot captured before some other push/replace (e.g. applying filters)
  // landed — otherwise this can win a race and clobber those params. The
  // `searchParams.get('topic') === selectedTopicId` guard above makes re-runs
  // from unrelated param changes (page, sort, ...) a no-op.
  }, [selectedTopicId, pathname, searchParams, router])

  return null
}

export function TopicProvider({ children }: { children: ReactNode }) {
  // 018-public-api-auth: /topics now requires a token — wait for AuthTokenProvider
  // to resolve one (real session or guest) before calling, so this doesn't race
  // the guest-token bootstrap on a fresh anonymous visit.
  const { token, isLoading: authLoading } = useAuthToken()

  const [topics, setTopics] = useState<Topic[]>([])
  const [selectedTopicId, setSelectedTopicIdState] = useState<string | null>(null)
  const [initialized, setInitialized] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  async function loadTopics() {
    const data = await fetchTopics()
    setTopics(data)
    const stored = localStorage.getItem(STORAGE_KEY)
    const valid = data.find(t => t.id === stored)
    const initial = valid ? stored : (data[0]?.id ?? null)
    setSelectedTopicIdState(prev => {
      if (prev && data.find(t => t.id === prev)) return prev
      if (initial) localStorage.setItem(STORAGE_KEY, initial)
      return initial
    })
    setInitialized(true)
  }

  useEffect(() => {
    if (authLoading || !token) return
    setIsLoading(true)
    loadTopics().finally(() => setIsLoading(false))
  }, [authLoading, token])

  function setSelectedTopicId(id: string) {
    setSelectedTopicIdState(id)
    localStorage.setItem(STORAGE_KEY, id)
  }

  async function refresh() {
    await loadTopics()
  }

  const selectedTopic = topics.find(t => t.id === selectedTopicId) ?? null

  return (
    <TopicContext.Provider value={{ topics, selectedTopicId, selectedTopic, setSelectedTopicId, refresh, isLoading }}>
      <Suspense fallback={null}>
        <TopicUrlSync
          topics={topics}
          selectedTopicId={selectedTopicId}
          initialized={initialized}
          onTopicFromUrl={setSelectedTopicId}
        />
      </Suspense>
      {children}
    </TopicContext.Provider>
  )
}

export function useTopic() {
  return useContext(TopicContext)
}