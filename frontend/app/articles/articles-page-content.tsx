'use client'

import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import Link from 'next/link'
import { fetchArticles, type Article } from '@/lib/api/articles'
import { searchArticles } from '@/lib/api/search'
import { ArticleCard, ArticleCardSkeleton } from '@/components/features/articles/article-card'
import { FilterBar } from '@/components/features/articles/filter-bar'
import { SortSelect } from '@/components/features/articles/sort-select'
import { SearchBar } from '@/components/features/articles/search-bar'
import { usePagination } from '@/hooks/use-pagination'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { ChevronLeft, ChevronRight, Newspaper, Lock, HelpCircle } from 'lucide-react'
import { useTopic, useI18n, useGuestMode } from '@/lib/providers'

const GUEST_PLACEHOLDER_ARTICLES: Article[] = Array.from({ length: 6 }, (_, i) => ({
  id: `guest-${i}`,
  title: 'Lorem ipsum dolor sit amet consectetur adipiscing elit',
  source: 'arxiv',
  content:
    'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor ' +
    'incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud ' +
    'exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.',
  published_at: new Date(Date.now() - i * 86400000).toISOString(),
  scraped_at: null,
  url: '#',
  metrics: {},
  view_count: 0,
}))

interface ArticlesPageContentProps {
  /** Server-rendered first page of results for the current URL's params, seeded from
   * `app/articles/page.tsx`'s SSR fetch. `undefined` when the server didn't fetch (no session —
   * see spec.md User Story 3) or the fetch failed (FR-007) — in that case this component behaves
   * exactly as it did pre-SSR, fetching client-side on mount. */
  initialArticles?: Article[]
  initialTotal?: number
}

export default function ArticlesPageContent({ initialArticles, initialTotal }: ArticlesPageContentProps) {
  const { data: session, status } = useSession()
  const token = (session as { accessToken?: string } | null)?.accessToken
  const { isGuestMode } = useGuestMode()
  const isPaywall = status === 'unauthenticated' && !isGuestMode
  const searchParams = useSearchParams()
  const { t, locale } = useI18n()
  const {
    page, sort, order, hasExplicitSort, favoritesOnly, searchQuery, setPage, setSort, setOrder, setFilters, setFavoritesOnly, setSearchQuery,
    aggregators, originalSources, tags, tagGroups,
    publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
    activeFilterCount,
  } = usePagination()
  const [articles, setArticles] = useState<Article[]>(initialArticles ?? [])
  const firstVectorArticleId = useMemo(
    () => articles.find(a => a.has_vectors)?.id,
    [articles]
  )
  const [total, setTotal] = useState(initialTotal ?? 0)
  const [isLoading, setIsLoading] = useState(initialArticles === undefined)
  // Consumed on the first effect run that actually reaches the fetch below (i.e. once
  // selectedTopicId has resolved) — skips exactly the one fetch that would otherwise duplicate
  // the SSR-seeded data for the current URL, while every subsequent params change still fetches
  // normally (FR-003/SC-004).
  const skipNextFetch = useRef(initialArticles !== undefined)
  const { selectedTopicId } = useTopic()
  const [openArticleId, setOpenArticleId] = useState<string | null>(
    () => searchParams.get('article')
  )
  // Hybrid (sparse+dense) search can surface semantically related articles that never
  // literally contain the query — this lets a visitor narrow back down to just the ones
  // that do (backend/services/search_service.py's exact_match flag). Defaults to on.
  const [exactMatchOnly, setExactMatchOnly] = useState(true)

  const fetchSearchParamsString = useMemo(() => {
    const p = new URLSearchParams(searchParams.toString())
    p.delete('article')
    // Favorites-only is applied client-side below (see displayedArticles), not re-fetched.
    p.delete('favorites_only')
    // topic is already tracked via selectedTopicId below; TopicUrlSync writing
    // it back into the URL after selection shouldn't itself trigger a second,
    // redundant fetch with identical params.
    p.delete('topic')
    return p.toString()
  }, [searchParams])

  // history.replaceState (not next/navigation's router.replace) so opening/closing the article
  // dialog only updates the URL for deep-linking/back-forward — it doesn't trigger a fresh
  // server render of this dynamic route, whose own SSR fetch result isn't used past mount anyway
  // (see initialArticles/initialTotal above) and doesn't depend on the `article` param at all.
  const handleArticleOpenChange = useCallback((articleId: string, open: boolean) => {
    setOpenArticleId(open ? articleId : null)
    const params = new URLSearchParams(searchParams.toString())
    if (open) {
      params.set('article', articleId)
    } else {
      params.delete('article')
    }
    window.history.replaceState(null, '', `/articles?${params.toString()}`)
  }, [searchParams])

  useEffect(() => {
    if (isPaywall) { setIsLoading(false); return }
    if (!selectedTopicId) return
    if (searchQuery) return // handled by the search effect below instead
    // Session resolution is itself async (useSession() starts at status: 'loading' with
    // token: undefined even for an already-signed-in visitor) — waiting for it to settle
    // before consuming skipNextFetch is what keeps the *real* first fetch (not this
    // transient one) from being the one that discards the SSR-seeded articles.
    if (status === 'loading') return
    if (skipNextFetch.current) {
      skipNextFetch.current = false
      setIsLoading(false)
      return
    }
    setIsLoading(true)

    fetchArticles(
      {
        page: isGuestMode ? 1 : page,
        topic_id: selectedTopicId,
        sort,
        order,
        aggregator: aggregators,
        original_source: originalSources,
        tag: tags,
        tag_group: tagGroups,
        published_after: publishedAfter,
        published_before: publishedBefore,
        scraped_after: scrapedAfter,
        scraped_before: scrapedBefore,
      },
      locale,
      token,
    )
      .then(data => { setArticles(data.items); setTotal(data.total) })
      .finally(() => setIsLoading(false))
  }, [fetchSearchParamsString, selectedTopicId, isPaywall, isGuestMode, locale, token, status, searchQuery])

  // FR-002/FR-006: hybrid search results replace the normal listing while a query is
  // applied. AbortController discards a superseded in-flight request's response so a
  // slow earlier search can never overwrite a faster later one (closes the gap flagged
  // in /speckit-analyze — FR-006 covers stale *search* responses, not just autocomplete).
  //
  // Filters (aggregator/original_source/tag/tag_group/date ranges) and `page` are always
  // forwarded — same as the plain-listing effect above. `sort`/`order` are forwarded only
  // when `hasExplicitSort` (the visitor actually picked one): search's default ordering is
  // RRF relevance, not a date sort, so unconditionally sending the URL's default
  // `sort=scraped_at` would silently replace relevance ranking with a date sort on every
  // search (023-article-search follow-up regression — filters/sort were previously dropped
  // entirely the moment a search was active; see backend/services/search_service.py).
  // `fetchSearchParamsString` (not individually-listed filter/sort deps) is what makes this
  // effect re-run on a filter/sort change while a search is already active — same pattern
  // the plain-listing effect above already relies on.
  useEffect(() => {
    if (isPaywall || !selectedTopicId || !searchQuery) return
    // A search actually running means we're past the "just mounted, must match the SSR
    // seed" window this guard exists for — if it's still true here (e.g. the page was
    // loaded directly at a `?q=...` URL, so the listing effect below hit its own
    // `!searchQuery` guard first and never got a chance to consume it), leaving it set
    // would wrongly skip the listing effect's *next* real fetch — the one that runs when
    // this search is later cleared — leaving stale search results on screen forever.
    skipNextFetch.current = false
    setIsLoading(true)
    const controller = new AbortController()

    searchArticles(
      {
        q: searchQuery, topic_id: selectedTopicId, page, exact_match_only: exactMatchOnly,
        aggregator: aggregators, original_source: originalSources, tag: tags, tag_group: tagGroups,
        published_after: publishedAfter, published_before: publishedBefore,
        scraped_after: scrapedAfter, scraped_before: scrapedBefore,
        ...(hasExplicitSort ? { sort, order } : {}),
      },
      locale, token, controller.signal,
    )
      .then(data => { setArticles(data.items); setTotal(data.total) })
      .catch(err => { if ((err as Error)?.name !== 'AbortError') throw err })
      .finally(() => { if (!controller.signal.aborted) setIsLoading(false) })

    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchSearchParamsString, selectedTopicId, searchQuery, exactMatchOnly, isPaywall, locale, token, hasExplicitSort])

  // A search keyword's match is language-specific (search_service.py's `lang`-scoped
  // inverted index/translation text) — a term that matched in one language's article text
  // has no guaranteed relationship to the same term in another language's translation, so
  // an active search is cleared whenever the visitor switches language rather than silently
  // re-running under a different `lang`. Skips the very first run (mount) — only an actual
  // *change* after that should clear anything; `isFirstLocaleRender` guards that instead of
  // listing `searchQuery`/`setSearchQuery` as deps, which would fire this on every keystroke
  // of an unrelated search instead of only on `locale` changing.
  const isFirstLocaleRender = useRef(true)
  useEffect(() => {
    if (isFirstLocaleRender.current) { isFirstLocaleRender.current = false; return }
    if (searchQuery) setSearchQuery('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale])

  // exact_match_only is applied server-side (backend/services/search_service.py) so
  // total/pagination stay consistent with what's actually returned — a client-side
  // per-page filter here would disagree with totalPages once boost_exact_match sorts
  // every exact match onto page 1, leaving later pages showing zero results despite
  // pagination still claiming more existed (023-article-search follow-up regression).
  // Favorites-only stays a pure client-side display filter — it's unrelated to search.
  const displayedArticles = favoritesOnly ? articles.filter(a => a.is_favorited) : articles

  function handleExactMatchOnlyChange(next: boolean) {
    setExactMatchOnly(next)
    if (page !== 1) setPage(1) // avoid stranding on a page the new (smaller) total can't fill
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <TooltipProvider>
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-border pb-6">
        <div className="flex items-center gap-3">
          <Newspaper className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold leading-none">{t('nav.articles')}</h1>
          <span className="inline-flex items-center h-6 px-2.5 rounded-full bg-muted text-xs font-medium text-muted-foreground">
            {favoritesOnly ? displayedArticles.length : total}
          </span>
        </div>
      </div>

      <SearchBar
        value={searchQuery}
        onSubmit={setSearchQuery}
        onClear={() => setSearchQuery('')}
        topicId={selectedTopicId ?? undefined}
        locale={locale}
        token={token}
      />

      {searchQuery && (
        <div className="flex items-center gap-1.5 w-fit">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
            <Checkbox
              checked={exactMatchOnly}
              onCheckedChange={(v) => handleExactMatchOnlyChange(v === true)}
              className="h-3.5 w-3.5"
            />
            {t('search.exactMatchOnly')}
          </label>
          <Tooltip>
            <TooltipTrigger asChild>
              <HelpCircle className="h-3 w-3 shrink-0 text-muted-foreground cursor-help" />
            </TooltipTrigger>
            <TooltipContent>
              {t('search.exactMatchOnlyTooltip')}
            </TooltipContent>
          </Tooltip>
        </div>
      )}

      <FilterBar
        aggregators={aggregators}
        originalSources={originalSources}
        tags={tags}
        tagGroups={tagGroups}
        publishedAfter={publishedAfter}
        publishedBefore={publishedBefore}
        scrapedAfter={scrapedAfter}
        scrapedBefore={scrapedBefore}
        activeFilterCount={activeFilterCount}
        favoritesOnly={favoritesOnly}
        onFavoritesToggle={setFavoritesOnly}
        onApply={setFilters}
      >
        <SortSelect sort={sort} order={order} onSortChange={setSort} onOrderChange={setOrder} />
      </FilterBar>

      {!isLoading && searchQuery && displayedArticles.length === 0 && (
        <p className="text-center text-sm text-muted-foreground py-12">{t('search.noResults')}</p>
      )}

      <div className="relative">
        <div className="grid gap-3 lg:grid-cols-2">
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => <ArticleCardSkeleton key={i} />)
            : (searchQuery && displayedArticles.length === 0)
            ? null
            : isPaywall
              ? GUEST_PLACEHOLDER_ARTICLES.map(a => (
                  <div key={a.id} className="select-none pointer-events-none blur-[2px] opacity-70">
                    <ArticleCard {...a} />
                  </div>
                ))
              : displayedArticles.map((a, i) => (
                  <ArticleCard
                    key={a.id}
                    {...a}
                    open={openArticleId === a.id}
                    onOpenChange={(v) => handleArticleOpenChange(a.id, v)}
                    isFirstTutorialTarget={a.id === firstVectorArticleId}
                    isStatsTutorialTarget={i === 0}
                    highlightQuery={searchQuery}
                  />
                ))
          }
        </div>

        {!isLoading && isPaywall && (
          <div className="absolute bottom-0 left-0 right-0 h-72 bg-gradient-to-t from-background via-background/90 to-transparent flex flex-col items-center justify-end pb-10 gap-4">
            <div className="flex items-center justify-center h-12 w-12 rounded-full border border-border bg-background shadow-sm">
              <Lock className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="text-center space-y-1.5">
              <p className="text-sm font-medium">{t('home.thereMoreToExplore')}</p>
              <p className="text-sm text-muted-foreground">
                <Link href="/login" className="font-medium text-primary underline underline-offset-4">{t('login.signIn')}</Link>
                {' '}{t('home.signInToReadMore')}
              </p>
            </div>
          </div>
        )}
      </div>

      {status === 'authenticated' && !favoritesOnly && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-4 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            className="rounded-full h-8 px-3 gap-1"
          >
            <ChevronLeft className="h-4 w-4" />
            {t('home.previous')}
          </Button>
          {(() => {
            const [before, after] = t('home.pageOf').replace('{total}', String(totalPages)).split('{page}')
            return (
              <span className="flex items-center gap-1 text-sm text-muted-foreground">
                {before}
                <input
                  key={page}
                  type="number"
                  min={1}
                  max={totalPages}
                  defaultValue={page}
                  className="w-12 h-7 text-sm text-center rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const val = parseInt((e.target as HTMLInputElement).value)
                      if (!isNaN(val) && val >= 1 && val <= totalPages) setPage(val)
                    }
                  }}
                />
                {after}
              </span>
            )
          })()}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
            className="rounded-full h-8 px-3 gap-1"
          >
            {t('home.next')}
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
    </TooltipProvider>
  )
}
