'use client'

import { Suspense } from 'react'
import SettingsPageContent from './settings-page-content'

export default function Page() {
  return (
    <Suspense fallback={<div />}>
      <SettingsPageContent />
    </Suspense>
  )
}