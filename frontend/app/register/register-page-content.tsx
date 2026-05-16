'use client'
import { useState } from 'react'
import { signIn } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Rss } from 'lucide-react'
import { registerUser } from '@/lib/api/auth'
import { useI18n } from '@/lib/providers'


export default function RegisterPageContent() {
    const { t } = useI18n()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const searchParams = useSearchParams()
  const alreadyRegistered = searchParams.get('error') === 'already_registered'

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const form = new FormData(e.currentTarget)
    try {
      const res = await registerUser({
        username: form.get('username') as string,
        password: form.get('password') as string,
        email: form.get('email') as string,
        name: (form.get('name') as string) || undefined,
      })
      if (res.status === 409) {
        setError(t('register.emailOrUsernameTaken'))
        return
      }
      if (!res.ok) {
        setError(t('register.registrationFailed'))
        return
      }
      // Auto sign-in after successful registration
      await signIn('credentials', {
        username: form.get('username'),
        password: form.get('password'),
        callbackUrl: '/',
      })
    } catch {
      setError(t('register.networkError'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl border border-border bg-card mb-2">
            <Rss className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">{t('register.createAccount')}</h1>
          <p className="text-sm text-muted-foreground">{t('register.newAccountsCreatedWithUserRole')}</p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
          {(error || alreadyRegistered) && (
            <div className="rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {alreadyRegistered ? t('register.googleAlreadyRegistered') : error}
              {alreadyRegistered && (
                <Link href="/login" className="underline font-medium">{t('register.signInInstead')} →</Link>
              )}
            </div>
          )}

          <Button
            variant="outline"
            className="w-full h-12 rounded-full font-semibold gap-2"
            onClick={() => signIn('google-register', { callbackUrl: '/' })}
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            {t('register.registerWithGoogle')}
          </Button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-muted-foreground">{t('register.or')}</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="name">{t('register.displayNameOptional')}</label>
              <input id="name" name="name"
                className="w-full h-12 px-4 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="email">{t('register.email')}</label>
              <input id="email" name="email" type="email" required
                className="w-full h-12 px-4 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="reg-username">{t('register.username')}</label>
              <input id="reg-username" name="username" required
                className="w-full h-12 px-4 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="reg-password">{t('register.password')}</label>
              <input id="reg-password" name="password" type="password" required
                className="w-full h-12 px-4 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <Button type="submit" disabled={loading}
              className="w-full h-12 rounded-full font-semibold">
              {loading ? t('register.creatingAccount') : t('register.createAccountBtn')}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            {t('register.alreadyHaveAccount')}{' '}
            <Link href="/login" className="font-medium text-foreground hover:underline">{t('register.signIn')}</Link>
          </p>
        </div>
      </div>
    </div>
  )
}