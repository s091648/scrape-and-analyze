'use client'
import useSWR from 'swr'
import {
  fetchLatestWeeklyReport, fetchWeeklyReports, fetchWeeklyReportWeeks, fetchWeeklyReportByWeek,
  type WeeklyReport,
} from '@/lib/api/weekly-reports'

export interface WeeklyReportFeedResult {
  latest: WeeklyReport | null
  /** `null` specifically means the list fetch itself failed (rejected) — distinct from a
   * genuinely empty list, so callers can decide whether to keep an SSR-seeded report on screen
   * over a transient failure (matches weekly-report-widget.tsx's pre-SWR behavior). */
  reports: WeeklyReport[] | null
  availableWeeks: string[]
  /** Populated only when `initialWeek` was requested and wasn't already present in `reports`. */
  deepLinkedReport: WeeklyReport | null
}

interface UseWeeklyReportFeedArgs {
  enabled: boolean
  topicId: string | null
  locale?: string
  initialWeek?: string | null
  /** SSR-seeded "latest report" for the very first paint — see weekly-report-widget.tsx's own
   * comment on why this deliberately does NOT skip the background fetch (unlike the other
   * feed hooks' fallbackData): the full reports list/available weeks always need a real fetch
   * regardless of the single seeded report, this only avoids a loading-skeleton flash. */
  fallbackData?: WeeklyReportFeedResult
}

export function useWeeklyReportFeed({
  enabled, topicId, locale, initialWeek, fallbackData,
}: UseWeeklyReportFeedArgs) {
  const key = enabled && topicId
    ? (['weekly-report-feed', topicId, locale ?? 'en', initialWeek ?? null] as const)
    : null

  const { data, isLoading } = useSWR<WeeklyReportFeedResult>(
    key,
    async () => {
      const [latestResult, listResult, weeksResult] = await Promise.allSettled([
        fetchLatestWeeklyReport(topicId as string, locale),
        fetchWeeklyReports(topicId as string, 10, 0, locale),
        fetchWeeklyReportWeeks(topicId as string),
      ])
      const latest = latestResult.status === 'fulfilled' ? latestResult.value : null
      const reports = listResult.status === 'fulfilled' ? listResult.value.items : null
      const availableWeeks = weeksResult.status === 'fulfilled' ? weeksResult.value : []

      let deepLinkedReport: WeeklyReport | null = null
      const list = reports ?? []
      if (initialWeek && !list.some(r => r.week_start_date.slice(0, 10) === initialWeek)) {
        deepLinkedReport = await fetchWeeklyReportByWeek(topicId as string, initialWeek, locale)
      }

      return { latest, reports, availableWeeks, deepLinkedReport }
    },
    // No revalidateOnMount override here — deliberately left at SWR's default (always fetch),
    // matching the "seed the fastest thing to show, but a real fetch always follows" intent above.
    { fallbackData },
  )

  return { data, isLoading }
}
