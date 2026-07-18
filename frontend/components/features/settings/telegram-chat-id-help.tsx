'use client'
import { useState } from 'react'
import { HelpCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useI18n } from '@/lib/providers'

interface Step {
  titleKey: string
  descriptionKey: string
  image: string
}

const STEPS: Step[] = [
  {
    titleKey: 'settings.telegramHelp.step1.title',
    descriptionKey: 'settings.telegramHelp.step1.description',
    image: '/help/telegram-chat-id/step-1.png',
  },
  {
    titleKey: 'settings.telegramHelp.step2.title',
    descriptionKey: 'settings.telegramHelp.step2.description',
    image: '/help/telegram-chat-id/step-2.png',
  },
  {
    titleKey: 'settings.telegramHelp.step3.title',
    descriptionKey: 'settings.telegramHelp.step3.description',
    image: '/help/telegram-chat-id/step-3.png',
  },
  {
    titleKey: 'settings.telegramHelp.step4.title',
    descriptionKey: 'settings.telegramHelp.step4.description',
    image: '/help/telegram-chat-id/step-4.png',
  },
]

export function TelegramChatIdHelp() {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [step, setStep] = useState(0)

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (!next) setStep(0)
  }

  const current = STEPS[step]
  const isLast = step === STEPS.length - 1

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label={t('settings.telegramHelp.openLabel')}
              className="cursor-pointer text-muted-foreground hover:text-foreground transition-colors"
            >
              <HelpCircle className="h-3.5 w-3.5" />
            </button>
          </TooltipTrigger>
          <TooltipContent>{t('settings.telegramHelp.openLabel')}</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <DialogContent className="sm:max-w-md">
        <div className="flex flex-col items-center gap-4 pt-2 text-center">
          <div className="flex items-center gap-2">
            {STEPS.map((s, i) => (
              <span
                key={s.image}
                className={`h-2 w-2 rounded-full transition-colors ${
                  i === step ? 'bg-primary' : 'bg-muted'
                }`}
              />
            ))}
          </div>
          <span className="text-xs text-muted-foreground">
            {t('tutorial.stepOf', { current: step + 1, total: STEPS.length })}
          </span>

          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={current.image}
            alt={t(current.titleKey)}
            className="h-72 w-full rounded-lg border border-border object-contain bg-muted/30"
          />

          <DialogTitle className="text-base font-semibold">{t(current.titleKey)}</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            {t(current.descriptionKey)}
          </DialogDescription>
        </div>

        <div className="flex items-center justify-between pt-2 w-full">
          <div>
            {step > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setStep(s => s - 1)}>
                <ChevronLeft className="h-4 w-4 mr-1" />
                {t('tutorial.back')}
              </Button>
            )}
          </div>
          {!isLast ? (
            <Button size="sm" onClick={() => setStep(s => s + 1)}>
              {t('tutorial.next')}
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          ) : (
            <Button size="sm" onClick={() => handleOpenChange(false)}>
              {t('tutorial.done')}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
