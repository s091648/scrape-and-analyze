'use client'

import * as TabsPrimitive from '@radix-ui/react-tabs'
import { TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useI18n } from '@/lib/providers'

export type TagMode = 'unsupervised' | 'semi_supervised' | 'supervised'

interface TagModeSelectorProps {
  value: TagMode
  onChange: (mode: TagMode) => void
  disabled?: boolean
}

export function TagModeSelector({ value, onChange, disabled = false }: TagModeSelectorProps) {
  const { t } = useI18n()
  return (
    <TabsPrimitive.Root value={value} onValueChange={v => onChange(v as TagMode)}>
      <TabsList>
        <TabsTrigger value="unsupervised" disabled={disabled}>
          {t('tags.unsupervised')}
        </TabsTrigger>
        <TabsTrigger value="semi_supervised" disabled={disabled}>
          {t('tags.semiSupervised')}
        </TabsTrigger>
        <TabsTrigger value="supervised" disabled={disabled}>
          {t('tags.supervised')}
        </TabsTrigger>
      </TabsList>
    </TabsPrimitive.Root>
  )
}
