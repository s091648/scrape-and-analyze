'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { redirect } from 'next/navigation'
import { apiFetch } from '@/lib/api-fetch'
import { ScraperSourceForm } from '@/components/scraper-source-form'
import { Switch } from '@/components/ui/switch'

export default function ScraperSettingsPage() {
  const { data: session, status } = useSession()
  const [settings, setSettings] = useState<any[]>([])

  if (status === 'unauthenticated') redirect('/login')
  if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') redirect('/login')

  const token = (session as any)?.accessToken

  useEffect(() => {
    if (!token) return
    apiFetch('/scraper-settings', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(setSettings)
  }, [token])

  async function handleCreate(data: any) {
    const res = await apiFetch('/scraper-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    })
    if (res.ok) {
      const newSetting = await res.json()
      setSettings(prev => [...prev, newSetting])
    }
  }

  async function toggleActive(id: string, is_active: boolean) {
    setSettings(prev => prev.map(s => s.id === id ? { ...s, is_active } : s))
    await apiFetch(`/scraper-settings/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ is_active }),
    })
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Scraper Settings</h1>
      <ul className="space-y-2">
        {settings.map(s => (
          <li key={s.id} className="border rounded p-3 flex items-center justify-between">
            <span>{s.name} ({s.source_type} / {s.frequency})</span>
            <Switch checked={s.is_active} onCheckedChange={v => toggleActive(s.id, v)} />
          </li>
        ))}
      </ul>
      <h2 className="text-xl font-semibold">Add Source</h2>
      <ScraperSourceForm onSubmit={handleCreate} />
    </div>
  )
}
