'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchAllMetricDefinitions, updateMetricDefinition, type MetricDefinitionAdmin } from '@/lib/api/metric-definitions'
import { MetricIconPicker } from '@/components/features/articles/metric-icon-picker'
import { useI18n } from '@/lib/providers'

export default function MetricDefinitionsPage() {
  const { t } = useI18n()
  const router = useRouter()
  const { data: session, status } = useSession()
  const [definitions, setDefinitions] = useState<MetricDefinitionAdmin[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
    if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') router.push('/settings')
  }, [status, session, router])

  const token = (session as any)?.accessToken

  useEffect(() => {
    if (!token) return
    setIsLoading(true)
    fetchAllMetricDefinitions(token)
      .then(setDefinitions)
      .finally(() => setIsLoading(false))
  }, [token])

  async function handleUpdate(id: string, data: { enabled?: boolean; icon_name?: string }) {
    setError(null)
    const prev = definitions
    setDefinitions(defs => defs.map(d => (d.id === id ? { ...d, ...data } : d)))
    try {
      await updateMetricDefinition(id, data, token)
    } catch {
      setDefinitions(prev)
      setError(t('admin.metricUpdateFailed'))
    }
  }

  return (
    <div className="max-w-3xl space-y-10">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('admin.metricDefinitions')}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t('admin.metricDefinitionsDescription')}</p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <div className="space-y-4">
          {[0, 1].map(i => (
            <div key={i} className="rounded-xl border border-border p-5 space-y-3">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-9 w-full" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {definitions.map(def => {
            const disabledIcons = new Map<string, string>()
            definitions.forEach(d => {
              if (d.id !== def.id && d.icon_name) disabledIcons.set(d.icon_name, t(d.label_i18n_key))
            })
            return (
              <div key={def.id} className="flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-5">
                <div className="flex items-center gap-3 min-w-0">
                  <MetricIconPicker
                    value={def.icon_name}
                    onChange={name => handleUpdate(def.id, { icon_name: name })}
                    disabledIcons={disabledIcons}
                    ariaLabel={`${def.metric_key} icon`}
                  />
                  <div className="min-w-0">
                    <h2 className="text-sm font-semibold truncate">{t(def.label_i18n_key)}</h2>
                    <p className="text-xs text-muted-foreground truncate">{def.metric_key}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-muted-foreground">
                    {def.enabled ? t('admin.metricEnabled') : t('admin.metricDisabled')}
                  </span>
                  <Switch
                    checked={def.enabled}
                    onCheckedChange={checked => handleUpdate(def.id, { enabled: checked })}
                    aria-label={def.metric_key}
                  />
                </div>
              </div>
            )
          })}
          {definitions.length === 0 && (
            <p className="text-sm text-muted-foreground">{t('admin.noMetricDefinitions')}</p>
          )}
        </div>
      )}
    </div>
  )
}
