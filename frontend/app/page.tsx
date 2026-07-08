'use client'

import { Suspense } from 'react'
import { InlineQABarWrapper } from '@/components/features/chat/InlineQABarWrapper'
import { WeeklyReportWidget } from '@/components/features/weekly-report/weekly-report-widget'
import { useTopic } from '@/lib/providers'

function HomeContent() {
  const { selectedTopicId } = useTopic()
  return (
    <WeeklyReportWidget topicId={selectedTopicId}>
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
