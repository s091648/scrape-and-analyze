'use client'

import { Suspense } from 'react'
import RegisterPageContent from './register-page-content'

export default function RegisterPage() {
  return (
      <Suspense fallback={<div />}>
        <RegisterPageContent />
      </Suspense>
    )
}
