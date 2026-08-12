'use client'

import { useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { InlineQABarWrapper } from '@/components/features/chat/InlineQABarWrapper'
import { WeeklyReportWidget } from '@/components/features/weekly-report/weekly-report-widget'
import type { WeeklyReport } from '@/lib/api/weekly-reports'
import { useTopic } from '@/lib/providers'

interface HomePageContentProps {
  /** Server-rendered latest report, seeded from `app/page.tsx`'s SSR fetch. `undefined` when the
   * server didn't fetch (no session — spec.md User Story 3) or the fetch failed (FR-007).
   * Trusted directly — `app/layout.tsx` seeds TopicProvider from the exact same `cache()`-shared
   * topic resolution `app/page.tsx` used to fetch this, so they can't disagree within one
   * request (see lib/server/ssr-fetch.ts's module doc comment). */
  initialReport?: WeeklyReport | null
}

export default function HomePageContent({ initialReport }: HomePageContentProps) {
  const { selectedTopicId } = useTopic()
  const searchParams = useSearchParams()
  // Captured once on mount: this is a one-time deep-link value (jump to a specific
  // week's report), not meant to keep re-syncing as the URL changes afterwards.
  const [initialWeek] = useState(() => searchParams.get('week'))
  return (
    <WeeklyReportWidget
      topicId={selectedTopicId}
      initialWeek={initialWeek}
      initialReport={initialReport}
    >
      {({ onSend, onConversationChange }) => (
        <InlineQABarWrapper className="w-full" onMessageSent={onSend} onConversationChange={onConversationChange} />
      )}
    </WeeklyReportWidget>
  )
}
