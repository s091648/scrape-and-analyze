'use client'
import { useEffect, useRef, useState } from 'react'
import { useSession, signOut } from 'next-auth/react'
import { useSearchParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { fetchMe, updateMe, changePassword, deleteMe, unlinkGoogle } from '@/lib/api/auth'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useI18n, useGuestMode } from '@/lib/providers'

interface Profile {
  id: string
  name: string | null
  email: string | null
  icon: string | null
  role: string
  google_id: string | null
  username: string | null
}

async function resizeToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = 128
      canvas.height = 128
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0, 128, 128)
      URL.revokeObjectURL(url)
      resolve(canvas.toDataURL('image/webp', 0.85))
    }
    img.onerror = reject
    img.src = url
  })
}

function initials(name: string | null | undefined): string {
  if (!name) return '?'
  return name
    .split(' ')
    .map(w => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export default function SettingsPageContent() {
  const { data: session } = useSession()
  const { t } = useI18n()
  const { isGuestMode } = useGuestMode()
  const token = (session as any)?.accessToken

  const [profile, setProfile] = useState<Profile | null>(null)
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [name, setName] = useState('')
  const [nameSaving, setNameSaving] = useState(false)
  const [nameMsg, setNameMsg] = useState<string | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [passwordMsg, setPasswordMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [passwordSaving, setPasswordSaving] = useState(false)
  const searchParams = useSearchParams()
  const router = useRouter()
  const [linkMsg, setLinkMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const linked = searchParams.get('linked')
    if (linked === 'success') {
      setLinkMsg({ ok: true, text: t('settings.googleAccountLinked') })
      setProfile(prev => prev ? { ...prev, google_id: '__linked__' } : prev)
      router.replace('/settings')
    } else if (linked === 'error') {
      setLinkMsg({ ok: false, text: t('settings.failedToLinkGoogle') })
      router.replace('/settings')
    }
  }, [searchParams, router, t])

  useEffect(() => {
    if (!token) return
    setIsLoading(true)
    fetchMe(token)
      .then((p) => {
        if (!p) return
        setProfile(p as unknown as Profile)
        setName(p.name ?? '')
        setAvatarSrc(p.icon ?? null)
      })
      .finally(() => setIsLoading(false))
  }, [token])

  if (isGuestMode) {
    return (
      <div className="space-y-4 max-w-md">
        <h2 className="text-xl font-bold">{t('guest.restrictedTitle')}</h2>
        <p className="text-sm text-muted-foreground">{t('guest.restrictedMessage')}</p>
        <div className="flex gap-3">
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2"
          >
            {t('login.signIn')}
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 py-2"
          >
            {t('login.register')}
          </Link>
        </div>
      </div>
    )
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const dataUrl = await resizeToBase64(file)
    const res = await updateMe(token, { icon: dataUrl })
    if (res.ok) {
      setAvatarSrc(dataUrl)
      setProfile(prev => prev ? { ...prev, icon: dataUrl } : prev)
    }
    // reset so same file can be re-selected
    e.target.value = ''
  }

  async function handleSaveName() {
    if (!name.trim()) return
    setNameSaving(true)
    setNameMsg(null)
    const res = await updateMe(token, { name: name.trim() })
    setNameSaving(false)
    if (res.ok) {
      setProfile(prev => prev ? { ...prev, name: name.trim() } : prev)
      setNameMsg(t('settings.saved'))
    } else {
      setNameMsg(t('settings.failedToSave'))
    }
    setTimeout(() => setNameMsg(null), 3000)
  }

  async function handleChangePassword() {
    if (!currentPassword || !newPassword) return
    setPasswordSaving(true)
    setPasswordMsg(null)
    const res = await changePassword(token, { current_password: currentPassword, new_password: newPassword })
    setPasswordSaving(false)
    if (res.ok) {
      setPasswordMsg({ ok: true, text: t('settings.passwordChangedSuccessfully') })
      setCurrentPassword('')
      setNewPassword('')
    } else {
      const data = await res.json().catch(() => ({}))
      setPasswordMsg({ ok: false, text: data?.detail ?? t('settings.failedToChangePassword') })
    }
  }

  async function handleDeleteAccount() {
    if (!confirm(t('settings.confirmDeleteAccount'))) return
    const res = await deleteMe(token)
    if (res.ok) {
      await signOut({ callbackUrl: '/login' })
    }
  }

  async function handleUnlinkGoogle() {
    if (!confirm(t('settings.unlinkGoogleAccount'))) return
    const res = await unlinkGoogle(token)
    if (res.ok) {
      setProfile(prev => prev ? { ...prev, google_id: null } : prev)
      setLinkMsg({ ok: true, text: t('settings.googleAccountUnlinked') })
    } else {
      const data = await res.json().catch(() => ({}))
      setLinkMsg({ ok: false, text: data?.detail ?? t('settings.failedToUnlink') })
    }
  }

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold">{t('settings.profile')}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t('settings.manageYourAccountSettings')}</p>
      </div>

      {isLoading ? (
        <div className="space-y-6">
          {/* Avatar section skeleton */}
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <Skeleton className="h-4 w-16" />
            <div className="flex items-center gap-6">
              <Skeleton className="w-32 h-32 rounded-full shrink-0" />
              <div className="space-y-2">
                <Skeleton className="h-3 w-48" />
                <Skeleton className="h-8 w-28 rounded-md" />
              </div>
            </div>
          </div>
          {/* Name section skeleton */}
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <Skeleton className="h-4 w-12" />
            <div className="flex gap-3">
              <Skeleton className="flex-1 h-10 rounded-lg" />
              <Skeleton className="h-10 w-16 rounded-md" />
            </div>
          </div>
          {/* Connected accounts skeleton */}
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <Skeleton className="h-4 w-36" />
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Skeleton className="h-5 w-5 rounded-sm" />
                <div className="space-y-1">
                  <Skeleton className="h-4 w-14" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
              <Skeleton className="h-8 w-24 rounded-md" />
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Avatar section */}
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <h2 className="font-semibold text-sm">{t('settings.avatar')}</h2>
            <div className="flex items-center gap-6">
              <div className="relative shrink-0">
                {avatarSrc ? (
                  <img
                    src={avatarSrc}
                    alt="Avatar"
                    width={128}
                    height={128}
                    className="w-32 h-32 rounded-full object-cover border border-border"
                  />
                ) : (
                  <div
                    className="w-32 h-32 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-3xl font-bold select-none"
                  >
                    {initials(profile?.name)}
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  {t('settings.avatarHelp')}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                >
                  {t('settings.changePhoto')}
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>
            </div>
          </div>

          {/* Name section */}
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <h2 className="font-semibold text-sm">{t('settings.name')}</h2>
            <div className="flex gap-3 items-center">
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder={t('settings.yourName')}
                className="flex-1 h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <Button size="sm" onClick={handleSaveName} disabled={nameSaving}>
                {nameSaving ? t('settings.saving') : t('settings.save')}
              </Button>
            </div>
            {nameMsg && (
              <p className="text-sm text-muted-foreground">{nameMsg}</p>
            )}
          </div>

          {/* Connected accounts */}
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <h2 className="font-semibold text-sm">{t('settings.connectedAccounts')}</h2>

            {linkMsg && (
              <p className={`text-sm ${linkMsg.ok ? 'text-green-600' : 'text-destructive'}`}>
                {linkMsg.text}
              </p>
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {/* Google icon */}
                <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                <div>
                  <p className="text-sm font-medium">{t('settings.google')}</p>
                  <p className="text-xs text-muted-foreground">
                    {profile?.google_id ? t('settings.connected') : t('settings.notConnected')}
                  </p>
                </div>
              </div>

              {profile && !profile.google_id && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    const res = await fetch('/api/link-google/start', {
                      headers: { Authorization: `Bearer ${token}` },
                    })
                    if (res.ok) {
                      const { url } = await res.json()
                      window.location.href = url
                    }
                  }}
                >
                  {t('settings.linkGoogle')}
                </Button>
              )}

              {profile?.google_id && profile.username && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
                  onClick={handleUnlinkGoogle}
                >
                  {t('settings.unlink')}
                </Button>
              )}
            </div>
          </div>

          {/* Password section — credentials users only */}
          {profile && !profile.google_id && (
            <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
              <h2 className="font-semibold text-sm">{t('settings.changePassword')}</h2>
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">{t('settings.currentPassword')}</label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={e => setCurrentPassword(e.target.value)}
                    className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium">{t('settings.newPassword')}</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              </div>
              <Button
                size="sm"
                onClick={handleChangePassword}
                disabled={passwordSaving || !currentPassword || !newPassword}
              >
                {passwordSaving ? t('settings.changing') : t('settings.changePasswordBtn')}
              </Button>
              {passwordMsg && (
                <p className={`text-sm ${passwordMsg.ok ? 'text-green-600' : 'text-destructive'}`}>
                  {passwordMsg.text}
                </p>
              )}
            </div>
          )}

          {/* Delete account section */}
          <div className="rounded-2xl border border-destructive/30 bg-card p-6 space-y-4">
            <h2 className="font-semibold text-sm text-destructive">{t('settings.dangerZone')}</h2>
            <p className="text-sm text-muted-foreground">
              {t('settings.permanentlyDeleteAccount')}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
              onClick={handleDeleteAccount}
            >
              {t('settings.deleteAccount')}
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
