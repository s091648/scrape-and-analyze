import SessionProviderWrapper from './session-provider'
import { I18nProvider } from './i18n-provider'
import { TopicProvider } from './topic-provider'
import { GuestModeProvider } from './guest-mode-provider'
import { TutorialProvider } from './tutorial-provider'
import { ChatQuotaProvider } from './chat-quota-provider'
import { ThemeProvider } from './theme-provider'
import { PinnedArticleProvider } from './pinned-article-provider'

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <SessionProviderWrapper>
        <ChatQuotaProvider>
          <TopicProvider>
            <I18nProvider>
              <PinnedArticleProvider>
                <GuestModeProvider>
                  <TutorialProvider>{children}</TutorialProvider>
                </GuestModeProvider>
              </PinnedArticleProvider>
            </I18nProvider>
          </TopicProvider>
        </ChatQuotaProvider>
      </SessionProviderWrapper>
    </ThemeProvider>
  )
}

export { useI18n } from './i18n-provider'
export { useTopic, type Topic } from './topic-provider'
export { useGuestMode } from './guest-mode-provider'
export { useTutorial } from './tutorial-provider'
export { useTheme } from './theme-provider'
export { useChatQuota, type Quota } from './chat-quota-provider'
export { usePinnedArticle, type PinnedArticle } from './pinned-article-provider'

