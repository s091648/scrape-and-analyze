'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { InlineQABarWrapper } from '@/components/features/chat/InlineQABarWrapper'
import { WeeklyReportWidget } from '@/components/features/weekly-report/weekly-report-widget'
import { useTopic } from '@/lib/providers'

function HomeContent() {
  const { selectedTopicId } = useTopic()
  const searchParams = useSearchParams()
  // Captured once on mount: TopicProvider rewrites the URL down to just `?topic=`
  // shortly after load, so `week` must be read before that happens.
  const [initialWeek] = useState(() => searchParams.get('week'))
  return (
    <WeeklyReportWidget topicId={selectedTopicId} initialWeek={initialWeek}>
      <InlineQABarWrapper className="w-full" />
    </WeeklyReportWidget>
  )
}

export default function Page() {
  return (
    <Suspense fallback={<div />}>
      <HomeContent />
    </Suspense>
  )
}
