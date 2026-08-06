import SessionProviderWrapper from './session-provider'
import { I18nProvider } from './i18n-provider'
import { TopicProvider } from './topic-provider'
import { GuestModeProvider } from './guest-mode-provider'
import { AuthTokenProvider } from './auth-token-provider'
import { TutorialProvider } from './tutorial-provider'
import { ChatQuotaProvider } from './chat-quota-provider'
import { ThemeProvider } from './theme-provider'
import { PinnedArticleProvider, PinnedReportProvider } from './pinned-article-provider'
import { FloatChatProvider } from './float-chat-provider'
import { InlineChatProvider } from './inline-chat-provider'

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <SessionProviderWrapper>
        <AuthTokenProvider>
          <ChatQuotaProvider>
            <TopicProvider>
              <I18nProvider>
                <PinnedArticleProvider>
                  <PinnedReportProvider>
                    {/* Mounted at the app root (not inside the chat components themselves) so an
                        in-flight stream survives route changes instead of being abandoned when
                        FloatingChatbotWrapper/InlineQABarWrapper unmount — see float-chat-provider.tsx. */}
                    <FloatChatProvider>
                      <InlineChatProvider>
                        <GuestModeProvider>
                          <TutorialProvider>{children}</TutorialProvider>
                        </GuestModeProvider>
                      </InlineChatProvider>
                    </FloatChatProvider>
                  </PinnedReportProvider>
                </PinnedArticleProvider>
              </I18nProvider>
            </TopicProvider>
          </ChatQuotaProvider>
        </AuthTokenProvider>
      </SessionProviderWrapper>
    </ThemeProvider>
  )
}

export { useI18n } from './i18n-provider'
export { useTopic, type Topic } from './topic-provider'
export { useGuestMode } from './guest-mode-provider'
export { useAuthToken } from './auth-token-provider'
export { useTutorial } from './tutorial-provider'
export { useTheme } from './theme-provider'
export { useChatQuota, type Quota } from './chat-quota-provider'
export { usePinnedArticle, usePinnedReport, type PinnedArticle } from './pinned-article-provider'
export { useFloatChat } from './float-chat-provider'
export { useInlineChat } from './inline-chat-provider'

