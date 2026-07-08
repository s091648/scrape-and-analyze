'use client'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Clock } from 'lucide-react'
import { type WeeklyReport } from '@/lib/api/weekly-reports'

interface WeeklyReportDetailDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  report: WeeklyReport | null
}

export function WeeklyReportDetailDialog({ open, onOpenChange, report }: WeeklyReportDetailDialogProps) {
  if (!report) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-border">
          <DialogTitle className="text-lg leading-snug pr-6">{report.title}</DialogTitle>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {new Date(report.week_start_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
            </span>
            <span className="text-xs text-muted-foreground">{report.article_count} articles</span>
          </div>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
            {report.summary_text}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  )
}
