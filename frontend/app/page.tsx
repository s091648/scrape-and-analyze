'use client'

import { Suspense } from 'react'
import { InlineQABarWrapper } from '@/components/features/chat/InlineQABarWrapper'
import { WeeklyReportWidget } from '@/components/features/weekly-report/weekly-report-widget'
import { useTopic } from '@/lib/providers'

function HomeContent() {
  const { selectedTopicId } = useTopic()
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] w-full max-w-2xl mx-auto">
      <WeeklyReportWidget topicId={selectedTopicId}>
        <InlineQABarWrapper className="w-full" />
      </WeeklyReportWidget>
    </div>
  )
}

export default function Page() {
  return (
    <Suspense fallback={<div />}>
      <HomeContent />
    </Suspense>
  )
}
