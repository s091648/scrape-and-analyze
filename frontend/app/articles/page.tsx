'use client'

import { Suspense } from 'react'
import HomePageContent from '../home-page-content'

export default function ArticlesPage() {
  return (
    <Suspense fallback={<div />}>
      <HomePageContent />
    </Suspense>
  )
}
