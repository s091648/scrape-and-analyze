'use client'
import { signIn, useSession } from 'next-auth/react'
import { useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Rss } from 'lucide-react'
import { useI18n } from '@/lib/providers'

export default function LoginPageContent() {
  const { status } = useSession()
  const router = useRouter()
  const { t } = useI18n()
  const [error, setError] = useState('')
  const searchParams = useSearchParams()

  if (status === 'authenticated') {
    router.replace('/')
    return null
  }
  const authError = searchParams.get('error')

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const result = await signIn('credentials', {
      username: form.get('username'),
      password: form.get('password'),
      redirect: false,
    })
    if (result?.error) setError(t('login.invalidCredentials'))
    else window.location.href = '/'
  }

  const notRegistered = authError === 'not_registered'
  const disabled = authError === 'account_disabled'
  const linkRequired = authError === 'link_required'

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border border-border bg-card mb-2">
            <Rss className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">{t('login.welcomeBack')}</h1>
          <p className="text-sm text-muted-foreground">{t('login.signInToYourAccount')}</p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
          {(error || notRegistered || disabled || linkRequired) && (
            <div className="rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive space-y-2">
              {error && <p>{error}</p>}
              {disabled && <p>{t('login.accountDisabled')}</p>}
              {notRegistered && (
                <div>
                  <p>{t('login.googleNotRegistered')}</p>
                  <Link href="/register" className="underline font-medium">
                    {t('login.createAccount')} →
                  </Link>
                </div>
              )}
              {linkRequired && (
                <p>
                  {t('login.emailAlreadyRegistered')}{t('login.signInWithUsername')}
                  <Link href="/settings" className="underline font-medium">{t('nav.settings')}</Link>.
                </p>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="username">{t('login.username')}</label>
              <input
                id="username"
                name="username"
                autoComplete="username"
                className="w-full h-14 px-5 rounded-lg border border-border bg-background text-sm transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="password">{t('login.password')}</label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                className="w-full h-14 px-5 rounded-lg border border-border bg-background text-sm transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <Button type="submit" className="w-full h-14 rounded-full text-base font-semibold">
              {t('login.signIn')}
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">{t('login.or')}</span>
            </div>
          </div>

          <Button
            variant="outline"
            className="w-full h-14 rounded-full text-base font-semibold gap-2"
            onClick={() => signIn('google-login', { callbackUrl: '/' })}
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            {t('login.signInWithGoogle')}
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            {t('login.noAccount')}{' '}
            <Link href="/register" className="font-medium text-foreground hover:underline">
              {t('login.register')}
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
