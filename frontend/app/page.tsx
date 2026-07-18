'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { InlineQABarWrapper } from '@/components/features/chat/InlineQABarWrapper'
import { WeeklyReportWidget } from '@/components/features/weekly-report/weekly-report-widget'
import { useTopic } from '@/lib/providers'

function HomeContent() {
  const { selectedTopicId } = useTopic()
  const searchParams = useSearchParams()
  // Captured once on mount: this is a one-time deep-link value (jump to a specific
  // week's report), not meant to keep re-syncing as the URL changes afterwards.
  const [initialWeek] = useState(() => searchParams.get('week'))
  return (
    <WeeklyReportWidget topicId={selectedTopicId} initialWeek={initialWeek}>
      {({ onSend, onConversationChange }) => (
        <InlineQABarWrapper className="w-full" onMessageSent={onSend} onConversationChange={onConversationChange} />
      )}
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
