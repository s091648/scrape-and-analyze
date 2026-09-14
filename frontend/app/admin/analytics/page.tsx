'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useI18n } from '@/lib/providers'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import {
  fetchAnalyticsOverview, type AnalyticsOverview, type AnalyticsWindow,
} from '@/lib/api/analytics'
import { ViewsTrendChart, TopicBarChart, Sparkline } from '@/components/features/analytics/charts'

const WINDOWS: AnalyticsWindow[] = [7, 30, 90]

export default function AnalyticsPage() {
  const { t } = useI18n()
  const router = useRouter()
  const { data: session, status } = useSession()

  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
    if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') router.push('/settings')
  }, [status, session, router])

  const token = (session as any)?.accessToken

  const [days, setDays] = useState<AnalyticsWindow>(30)
  const [data, setData] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!token) return
    setLoading(true)
    setError(null)
    fetchAnalyticsOverview(days, token)
      .then(setData)
      .catch(() => setError(t('admin.analyticsLoadError')))
      .finally(() => setLoading(false))
  }, [token, days, t])

  useEffect(() => { load() }, [load])

  return (
    <div className="max-w-6xl space-y-6">
      <div className="border-b border-border pb-6 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">{t('admin.analytics')}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t('admin.analyticsSubtitle')}</p>
        </div>
        <div className="flex gap-1">
          {WINDOWS.map(w => (
            <button
              key={w}
              onClick={() => setDays(w)}
              className={cn(
                'text-xs px-2.5 py-1 rounded-lg border transition-colors cursor-pointer',
                days === w
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-border text-muted-foreground hover:border-foreground hover:text-foreground',
              )}
            >
              {t('admin.analyticsWindowDays', { days: String(w) })}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="text-sm text-destructive">{error}</div>}

      {loading || !data ? (
        <div className="space-y-6">
          <Skeleton className="h-56 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      ) : (
        <>
          {/* A — site-wide daily views */}
          <section className="border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold mb-3">{t('admin.analyticsDailyViews')}</h2>
            {data.daily_totals.length === 0
              ? <EmptyHint text={t('admin.analyticsNoData')} />
              : <ViewsTrendChart data={data.daily_totals} />}
          </section>

          {/* B — trending articles */}
          <section className="border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold mb-1">
              {t('admin.analyticsTrending', { days: String(days) })}
            </h2>
            <p className="text-xs text-muted-foreground mb-3">{t('admin.analyticsTrendingHint')}</p>
            {data.trending.length === 0 ? (
              <EmptyHint text={t('admin.analyticsNoData')} />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b border-border">
                      <th className="py-2 pr-2 w-8">#</th>
                      <th className="py-2 pr-3">{t('admin.analyticsColTitle')}</th>
                      <th className="py-2 pr-3 hidden sm:table-cell">{t('admin.analyticsColSource')}</th>
                      <th className="py-2 pr-3 hidden md:table-cell">{t('admin.analyticsColTopic')}</th>
                      <th className="py-2 pr-3 text-right whitespace-nowrap">{t('admin.analyticsColWindowViews', { days: String(days) })}</th>
                      <th className="py-2 pr-3 text-right whitespace-nowrap hidden sm:table-cell">{t('admin.analyticsColTotalViews')}</th>
                      <th className="py-2 hidden lg:table-cell">{t('admin.analyticsColTrend')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.trending.map((a, i) => (
                      <tr key={a.article_id} className="border-b border-border/60 last:border-0">
                        <td className="py-2 pr-2 text-muted-foreground tabular-nums">{i + 1}</td>
                        <td className="py-2 pr-3 max-w-xs">
                          <Link href={`/articles/${a.article_id}`} className="text-primary hover:underline line-clamp-2">
                            {a.title}
                          </Link>
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground hidden sm:table-cell">{a.source ?? '—'}</td>
                        <td className="py-2 pr-3 text-muted-foreground hidden md:table-cell">{a.topic ?? '—'}</td>
                        <td className="py-2 pr-3 text-right tabular-nums font-medium">{a.window_views.toLocaleString()}</td>
                        <td className="py-2 pr-3 text-right tabular-nums text-muted-foreground hidden sm:table-cell">{a.total_views.toLocaleString()}</td>
                        <td className="py-2 hidden lg:table-cell"><Sparkline data={a.sparkline} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* C — views by topic */}
          <section className="border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold mb-3">
              {t('admin.analyticsByTopic', { days: String(days) })}
            </h2>
            {data.by_topic.length === 0
              ? <EmptyHint text={t('admin.analyticsNoData')} />
              : <TopicBarChart data={data.by_topic} />}
          </section>

          {/* D — all-time top */}
          <section className="border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold mb-1">{t('admin.analyticsAllTimeTop')}</h2>
            <p className="text-xs text-muted-foreground mb-3">{t('admin.analyticsAllTimeTopHint')}</p>
            {data.all_time_top.length === 0 ? (
              <EmptyHint text={t('admin.analyticsNoData')} />
            ) : (
              <ol className="space-y-1.5 text-sm">
                {data.all_time_top.map((a, i) => (
                  <li key={a.article_id} className="flex items-baseline gap-3">
                    <span className="text-muted-foreground tabular-nums w-5 text-right shrink-0">{i + 1}</span>
                    <Link href={`/articles/${a.article_id}`} className="text-primary hover:underline line-clamp-1 flex-1">
                      {a.title}
                    </Link>
                    <span className="tabular-nums text-muted-foreground shrink-0">{a.total_views.toLocaleString()}</span>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <p className="text-xs text-muted-foreground">{t('admin.analyticsFootnote')}</p>
        </>
      )}
    </div>
  )
}

function EmptyHint({ text }: { text: string }) {
  return <div className="text-sm text-muted-foreground py-8 text-center">{text}</div>
}
