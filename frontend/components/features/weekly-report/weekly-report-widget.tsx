'use client'
import { useEffect, useState } from 'react'
import { NativeSelect } from '@/components/ui/native-select'
import { WeeklyReportCard } from './weekly-report-card'
import { WeeklyReportSkeleton } from './weekly-report-skeleton'
import { fetchLatestWeeklyReport, fetchWeeklyReports, type WeeklyReport } from '@/lib/api/weekly-reports'

interface WeeklyReportWidgetProps {
  topicId: string | null
}

export function WeeklyReportWidget({ topicId }: WeeklyReportWidgetProps) {
  const [reports, setReports] = useState<WeeklyReport[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!topicId) return
    setLoading(true)
    Promise.allSettled([
      fetchLatestWeeklyReport(topicId),
      fetchWeeklyReports(topicId, 10, 0),
    ]).then(([latestResult, listResult]) => {
      const list = listResult.status === 'fulfilled' ? listResult.value.items : []
      setReports(list)
      if (latestResult.status === 'fulfilled' && latestResult.value) {
        setSelectedId(latestResult.value.id)
      } else if (list.length > 0) {
        setSelectedId(list[0].id)
      }
    }).finally(() => setLoading(false))
  }, [topicId])

  const selected = reports.find(r => r.id === selectedId) ?? null

  if (!topicId) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Weekly Report</h2>
        {reports.length > 1 && (
          <NativeSelect
            size="sm"
            value={selectedId ?? ''}
            onChange={e => setSelectedId(e.target.value)}
          >
            {reports.map(r => (
              <option key={r.id} value={r.id}>
                {new Date(r.week_start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </option>
            ))}
          </NativeSelect>
        )}
      </div>
      {loading ? (
        <WeeklyReportSkeleton />
      ) : selected ? (
        <WeeklyReportCard report={selected} />
      ) : (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center">
          <p className="text-sm text-muted-foreground">No report for this week yet.</p>
        </div>
      )}
    </div>
  )
}
