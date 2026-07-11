import { type WeeklyReport } from '@/lib/api/weekly-reports'
import { useI18n } from '@/lib/providers'

interface WeeklyReportCardProps {
  report: WeeklyReport
}

export function WeeklyReportCard({ report }: WeeklyReportCardProps) {
  const { t, locale } = useI18n()
  const coverStyle = report.cover_image_url
    ? { backgroundImage: `url(${report.cover_image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' }
    : { backgroundColor: 'hsl(var(--muted))' }

  return (
    <div className="rounded-2xl border border-border overflow-hidden">
      <div style={{ ...coverStyle, minHeight: '160px', display: 'flex', alignItems: 'flex-end' }}>
        <div className="bg-background/85 backdrop-blur-sm m-4 p-4 rounded-xl w-[calc(100%-2rem)]">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            {new Date(report.week_start_date).toLocaleDateString(locale === 'zh-TW' ? 'zh-TW' : 'en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
          </p>
          <h3 className="text-base font-bold leading-snug mb-2">{report.title}</h3>
          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">{report.summary_text}</p>
          <p className="text-xs text-muted-foreground mt-2">{t('weeklyReport.articleCount', { count: report.article_count })}</p>
        </div>
      </div>
    </div>
  )
}
