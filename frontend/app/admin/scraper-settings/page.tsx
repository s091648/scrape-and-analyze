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
  if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') redirect('/settings')

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
    <div className="max-w-3xl space-y-10">
      {/* Header */}
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">Scraper Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your news sources and scraping schedule.</p>
      </div>

      {/* Sources list */}
      <div className="space-y-2">
        <h2 className="text-base font-semibold">Active Sources</h2>
        {settings.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center border border-dashed border-border rounded-2xl">
            No sources yet. Add one below.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-2xl border border-border overflow-hidden">
            {settings.map(s => (
              <li key={s.id} className="flex items-center justify-between px-5 py-4 bg-card hover:bg-muted/40 transition-colors duration-150">
                <div className="space-y-0.5">
                  <p className="text-sm font-medium">{s.name}</p>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-5 px-2 rounded-full border border-border text-xs text-muted-foreground">
                      {s.source_type}
                    </span>
                    <span className="inline-flex h-5 px-2 rounded-full border border-border text-xs text-muted-foreground">
                      {s.frequency}
                    </span>
                  </div>
                </div>
                <Switch checked={s.is_active} onCheckedChange={v => toggleActive(s.id, v)} />
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Add form */}
      <div className="space-y-4">
        <h2 className="text-base font-semibold">Add Source</h2>
        <ScraperSourceForm onSubmit={handleCreate} />
      </div>
    </div>
  )
}
