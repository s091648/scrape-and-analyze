import SessionProviderWrapper from '@/components/providers/session-provider'
import { I18nProvider } from './i18n-provider'
import { TopicProvider } from './topic-provider'

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <SessionProviderWrapper>
      <I18nProvider>
        <TopicProvider>{children}</TopicProvider>
      </I18nProvider>
    </SessionProviderWrapper>
  )
}

export { useI18n } from './i18n-provider'
export { useTopic, type Topic } from './topic-provider'
