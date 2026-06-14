'use client'

import { Suspense } from 'react'
import { InlineQABarWrapper } from '@/components/features/rag/InlineQABarWrapper'

export default function Page() {
  return (
    <Suspense fallback={<div />}>
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <InlineQABarWrapper className="w-full max-w-2xl" />
      </div>
    </Suspense>
  )
}
