'use client'
import { useEffect, useRef, useState } from 'react'
import { useSession, signOut } from 'next-auth/react'
import { apiFetch } from '@/lib/api-fetch'
import { Button } from '@/components/ui/button'

interface Profile {
  id: string
  name: string | null
  email: string | null
  icon: string | null
  role: string
  google_id: string | null
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

export default function SettingsPage() {
  const { data: session } = useSession()
  const token = (session as any)?.accessToken

  const [profile, setProfile] = useState<Profile | null>(null)
  const [avatarSrc, setAvatarSrc] = useState<string | null>(null)

  // Name field
  const [name, setName] = useState('')
  const [nameSaving, setNameSaving] = useState(false)
  const [nameMsg, setNameMsg] = useState<string | null>(null)

  // Password fields
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [passwordMsg, setPasswordMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [passwordSaving, setPasswordSaving] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!token) return
    apiFetch('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then((p: Profile) => {
        setProfile(p)
        setName(p.name ?? '')
        setAvatarSrc(p.icon ?? null)
      })
  }, [token])

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const dataUrl = await resizeToBase64(file)
    const res = await apiFetch('/auth/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ icon: dataUrl }),
    })
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
    const res = await apiFetch('/auth/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: name.trim() }),
    })
    setNameSaving(false)
    if (res.ok) {
      setProfile(prev => prev ? { ...prev, name: name.trim() } : prev)
      setNameMsg('Saved.')
    } else {
      setNameMsg('Failed to save.')
    }
    setTimeout(() => setNameMsg(null), 3000)
  }

  async function handleChangePassword() {
    if (!currentPassword || !newPassword) return
    setPasswordSaving(true)
    setPasswordMsg(null)
    const res = await apiFetch('/auth/me/password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    })
    setPasswordSaving(false)
    if (res.ok) {
      setPasswordMsg({ ok: true, text: 'Password changed successfully.' })
      setCurrentPassword('')
      setNewPassword('')
    } else {
      const data = await res.json().catch(() => ({}))
      setPasswordMsg({ ok: false, text: data?.detail ?? 'Failed to change password.' })
    }
  }

  async function handleDeleteAccount() {
    if (!confirm('Are you sure you want to delete your account? This action cannot be undone.')) return
    const res = await apiFetch('/auth/me', {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) {
      await signOut({ callbackUrl: '/login' })
    }
  }

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your account settings</p>
      </div>

      {/* Avatar section */}
      <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
        <h2 className="font-semibold text-sm">Avatar</h2>
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
              JPG, PNG, or GIF. Max display size 128&times;128px.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              Change photo
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
        <h2 className="font-semibold text-sm">Name</h2>
        <div className="flex gap-3 items-center">
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Your name"
            className="flex-1 h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <Button size="sm" onClick={handleSaveName} disabled={nameSaving}>
            {nameSaving ? 'Saving…' : 'Save'}
          </Button>
        </div>
        {nameMsg && (
          <p className="text-sm text-muted-foreground">{nameMsg}</p>
        )}
      </div>

      {/* Password section — credentials users only */}
      {profile && !profile.google_id && (
        <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
          <h2 className="font-semibold text-sm">Change password</h2>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Current password</label>
              <input
                type="password"
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">New password</label>
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
            {passwordSaving ? 'Changing…' : 'Change password'}
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
        <h2 className="font-semibold text-sm text-destructive">Danger zone</h2>
        <p className="text-sm text-muted-foreground">
          Permanently delete your account and all associated data. This cannot be undone.
        </p>
        <Button
          variant="outline"
          size="sm"
          className="text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
          onClick={handleDeleteAccount}
        >
          Delete account
        </Button>
      </div>
    </div>
  )
}
