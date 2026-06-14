import SessionProviderWrapper from './session-provider'
import { I18nProvider } from './i18n-provider'
import { TopicProvider } from './topic-provider'
import { GuestModeProvider } from './guest-mode-provider'
import { ThemeProvider } from './theme-provider'

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <SessionProviderWrapper>
        <TopicProvider>
          <I18nProvider>
            <GuestModeProvider>{children}</GuestModeProvider>
          </I18nProvider>
        </TopicProvider>
      </SessionProviderWrapper>
    </ThemeProvider>
  )
}

export { useI18n } from './i18n-provider'
export { useTopic, type Topic } from './topic-provider'
export { useGuestMode } from './guest-mode-provider'
export { useTheme } from './theme-provider'
