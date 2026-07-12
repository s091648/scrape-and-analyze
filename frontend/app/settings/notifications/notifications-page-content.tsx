'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import Link from 'next/link'
import { fetchTopics, type Topic } from '@/lib/api/topics'
import {
  fetchSubscriptions, subscribeToTopic, unsubscribeTopic,
  fetchNotificationSettings, updateNotificationSettings, type NotificationSettings,
} from '@/lib/api/user'
import { Button } from '@/components/ui/button'
import { Dropdown } from '@/components/ui/dropdown'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleRow } from '@/components/ui/toggle-row'
import { TelegramChatIdHelp } from '@/components/features/settings/telegram-chat-id-help'
import { useI18n, useGuestMode } from '@/lib/providers'

export default function NotificationsPageContent() {
  const { data: session } = useSession()
  const { t } = useI18n()
  const { isGuestMode } = useGuestMode()
  const token = (session as any)?.accessToken

  const [isLoading, setIsLoading] = useState(true)
  const [topics, setTopics] = useState<Topic[]>([])
  const [subscribedTopicIds, setSubscribedTopicIds] = useState<Set<string>>(new Set())
  const [subLoading, setSubLoading] = useState<string | null>(null)

  const [notifSettings, setNotifSettings] = useState<NotificationSettings>({
    email_enabled: false,
    telegram_chat_id: null,
    telegram_enabled: false,
    locale: 'en',
  })
  const [notifSaving, setNotifSaving] = useState(false)
  const [notifMsg, setNotifMsg] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (!token) return
    setIsLoading(true)
    void Promise.allSettled([
      fetchTopics().then(setTopics),
      fetchSubscriptions(token).then(d => setSubscribedTopicIds(new Set(d.topic_ids))),
      fetchNotificationSettings(token).then(setNotifSettings),
    ]).finally(() => setIsLoading(false))
  }, [token])

  async function handleToggleSubscription(topicId: string) {
    setSubLoading(topicId)
    try {
      if (subscribedTopicIds.has(topicId)) {
        await unsubscribeTopic(topicId, token)
        setSubscribedTopicIds(prev => { const s = new Set(prev); s.delete(topicId); return s })
      } else {
        await subscribeToTopic(topicId, token)
        setSubscribedTopicIds(prev => new Set([...prev, topicId]))
      }
    } finally {
      setSubLoading(null)
    }
  }

  async function handleSaveNotifSettings() {
    setNotifSaving(true)
    setNotifMsg(null)
    try {
      const updated = await updateNotificationSettings(notifSettings, token)
      setNotifSettings(updated)
      setNotifMsg({ ok: true, text: t('settings.notifSettingsSaved') })
    } catch {
      setNotifMsg({ ok: false, text: t('settings.notifSettingsFailedToSave') })
    } finally {
      setNotifSaving(false)
      setTimeout(() => setNotifMsg(null), 3000)
    }
  }

  if (isGuestMode) {
    return (
      <div className="space-y-4 max-w-md">
        <h2 className="text-xl font-bold">{t('guest.restrictedTitle')}</h2>
        <p className="text-sm text-muted-foreground">{t('guest.restrictedMessage')}</p>
        <div className="flex gap-3">
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 border border-input bg-background hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2"
          >
            {t('login.signIn')}
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 py-2"
          >
            {t('login.register')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold">{t('settings.notificationSettings')}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t('settings.manageNotificationsDescription')}</p>
      </div>

      {isLoading ? (
        <div className="space-y-6">
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <Skeleton className="h-4 w-40" />
            <div className="space-y-2">
              <Skeleton className="h-8 w-full rounded-lg" />
              <Skeleton className="h-8 w-full rounded-lg" />
            </div>
          </div>
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-28 rounded-md" />
          </div>
        </div>
      ) : (
        <>
          {/* Topic subscriptions section */}
          {topics.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
              <h2 className="font-semibold text-sm">{t('settings.weeklyReportSubscriptions')}</h2>
              <p className="text-xs text-muted-foreground">{t('settings.weeklyReportSubscriptionsHelp')}</p>
              <div className="space-y-2">
                {topics.map(topic => (
                  <ToggleRow
                    key={topic.id}
                    label={
                      <span className="flex items-center gap-2">
                        {topic.color_hex && (
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full border border-border"
                            style={{ backgroundColor: topic.color_hex }}
                          />
                        )}
                        {topic.display_name}
                      </span>
                    }
                    description={topic.description ?? undefined}
                    checked={subscribedTopicIds.has(topic.id)}
                    disabled={subLoading === topic.id}
                    onCheckedChange={() => handleToggleSubscription(topic.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Notification settings section */}
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <h2 className="font-semibold text-sm">{t('settings.notificationSettings')}</h2>
            <div className="space-y-3">
              <ToggleRow
                label={t('settings.emailNotifications')}
                checked={notifSettings.email_enabled}
                onCheckedChange={v => setNotifSettings(prev => ({ ...prev, email_enabled: v }))}
              />
              <ToggleRow
                label={t('settings.telegramNotifications')}
                checked={notifSettings.telegram_enabled}
                onCheckedChange={v => setNotifSettings(prev => ({ ...prev, telegram_enabled: v }))}
              />
              {notifSettings.telegram_enabled && (
                <div className="space-y-1.5 pl-4 border-l-2 border-border">
                  <label className="flex items-center gap-1.5 text-sm font-medium">
                    {t('settings.telegramChatId')}
                    <TelegramChatIdHelp />
                  </label>
                  <input
                    type="text"
                    value={notifSettings.telegram_chat_id ?? ''}
                    onChange={e => setNotifSettings(prev => ({ ...prev, telegram_chat_id: e.target.value || null }))}
                    placeholder={t('settings.telegramChatIdPlaceholder')}
                    className="w-full h-10 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
              )}
              <div className="space-y-1.5">
                <label className="text-sm font-medium">{t('settings.notificationLanguage')}</label>
                <Dropdown
                  aria-label={t('settings.notificationLanguage')}
                  value={notifSettings.locale}
                  onChange={v => setNotifSettings(prev => ({ ...prev, locale: v }))}
                  className="w-full h-10 px-3"
                  options={[
                    { value: 'en', label: t('settings.languageEnglish') },
                    { value: 'zh-TW', label: t('settings.languageZhTw') },
                  ]}
                />
              </div>
            </div>
            <Button size="sm" onClick={handleSaveNotifSettings} disabled={notifSaving}>
              {notifSaving ? t('settings.saving') : t('settings.saveNotificationSettings')}
            </Button>
            {notifMsg && (
              <p className={`text-sm ${notifMsg.ok ? 'text-green-600' : 'text-destructive'}`}>{notifMsg.text}</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
