'use client'

import { X } from 'lucide-react'
import { useI18n } from '@/lib/providers'
import { ISO_ALPHA2_TO_NAME } from '@/lib/iso-country-codes'
import type { LogFilter } from './logs-table'

/** The active click-to-filter selection shown above the log tables, with a clear button.
 * Presentational only — the filter state is owned by LogsTab (monitoring-content.tsx). */
export function LogFilterChip({
  filter,
  onClear,
}: {
  filter: LogFilter | null
  onClear: () => void
}) {
  const { t } = useI18n()
  if (!filter) return null

  const fieldLabel =
    filter.type === 'country' ? t('admin.logColumnCountry') : t('admin.logColumnSession')
  const valueLabel =
    filter.type === 'country' ? ISO_ALPHA2_TO_NAME[filter.value] ?? filter.value : filter.value

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground">{t('admin.logFilterActive')}</span>
      <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-medium">
        <span className="text-muted-foreground">{fieldLabel}:</span>
        <span className="font-mono">{valueLabel}</span>
        <button
          type="button"
          onClick={onClear}
          aria-label={t('admin.logFilterClear')}
          className="text-muted-foreground hover:text-foreground cursor-pointer"
        >
          <X className="h-3 w-3" />
        </button>
      </span>
    </div>
  )
}
