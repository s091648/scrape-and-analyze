'use client'
import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

interface AccordionSectionProps {
  title: string
  badge?: number
  defaultOpen?: boolean
  children: React.ReactNode
}

export function AccordionSection({ title, badge, defaultOpen = true, children }: AccordionSectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 bg-card hover:bg-muted/40 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold">{title}</span>
          {badge !== undefined && (
            <span className="inline-flex h-5 min-w-5 px-1.5 rounded-full bg-muted text-xs text-muted-foreground items-center justify-center">
              {badge}
            </span>
          )}
        </div>
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <div className="px-4 pb-4 pt-2 space-y-3 bg-muted/20">{children}</div>
      )}
    </div>
  )
}
