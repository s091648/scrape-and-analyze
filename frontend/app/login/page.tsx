'use client'

import { Suspense } from 'react'
import LoginPageContent from './login-page-content'

export default function LoginPage() {
  return (
    <Suspense>
      <LoginPageContent />
    </Suspense>
  )
}