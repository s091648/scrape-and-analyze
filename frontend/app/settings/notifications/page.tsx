'use client'

import { Suspense } from 'react'
import NotificationsPageContent from './notifications-page-content'

export default function Page() {
  return (
    <Suspense fallback={<div />}>
      <NotificationsPageContent />
    </Suspense>
  )
}
