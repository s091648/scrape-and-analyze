'use client'

import { Suspense } from 'react'
import RegisterPageContent from './register-page-content'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export default function RegisterPage() {
  return (
      <Suspense fallback={<div />}>
        <RegisterPageContent />
      </Suspense>
    )
}
