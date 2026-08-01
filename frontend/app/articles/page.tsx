'use client'

import { Suspense } from 'react'
import ArticlesPageContent from './articles-page-content'

export default function ArticlesPage() {
  return (
    <Suspense fallback={<div />}>
      <ArticlesPageContent />
    </Suspense>
  )
}
