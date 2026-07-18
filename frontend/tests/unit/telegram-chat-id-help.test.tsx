import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { TelegramChatIdHelp } from '@/components/features/settings/telegram-chat-id-help'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, any>) => {
      const map: Record<string, string> = {
        'settings.telegramHelp.openLabel': 'How to find your chat ID',
        'settings.telegramHelp.step1.title': 'Step 1',
        'settings.telegramHelp.step1.description': 'Open Telegram',
        'settings.telegramHelp.step2.title': 'Step 2',
        'settings.telegramHelp.step2.description': 'Search the bot',
        'settings.telegramHelp.step3.title': 'Step 3',
        'settings.telegramHelp.step3.description': 'Send a message',
        'settings.telegramHelp.step4.title': 'Step 4',
        'settings.telegramHelp.step4.description': 'Copy the chat ID',
        'tutorial.stepOf': `Step ${params?.current ?? 1} of ${params?.total ?? 1}`,
        'tutorial.back': 'Back',
        'tutorial.next': 'Next',
        'tutorial.done': 'Done',
      }
      return map[key] ?? key
    },
  }),
}))

describe('TelegramChatIdHelp', () => {
  beforeEach(() => vi.clearAllMocks())

  function openDialog() {
    fireEvent.click(screen.getByLabelText('How to find your chat ID'))
  }

  it('does not show dialog content initially', () => {
    render(<TelegramChatIdHelp />)
    expect(screen.queryByText('Step 1')).toBeNull()
  })

  it('opens dialog and shows step 1 when trigger is clicked', async () => {
    render(<TelegramChatIdHelp />)
    openDialog()
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
    expect(screen.getByText('Open Telegram')).toBeDefined()
    expect(screen.getByText('Step 1 of 4')).toBeDefined()
  })

  it('does not show a Back button on the first step', async () => {
    render(<TelegramChatIdHelp />)
    openDialog()
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
    expect(screen.queryByText('Back')).toBeNull()
  })

  it('advances to the next step when Next is clicked', async () => {
    render(<TelegramChatIdHelp />)
    openDialog()
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
    fireEvent.click(screen.getByText('Next'))
    await waitFor(() => expect(screen.getByText('Step 2')).toBeDefined())
    expect(screen.getByText('Search the bot')).toBeDefined()
    expect(screen.getByText('Step 2 of 4')).toBeDefined()
  })

  it('goes back to the previous step when Back is clicked', async () => {
    render(<TelegramChatIdHelp />)
    openDialog()
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
    fireEvent.click(screen.getByText('Next'))
    await waitFor(() => expect(screen.getByText('Step 2')).toBeDefined())
    fireEvent.click(screen.getByText('Back'))
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
  })

  it('shows Done instead of Next on the last step', async () => {
    render(<TelegramChatIdHelp />)
    openDialog()
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
    fireEvent.click(screen.getByText('Next'))
    await waitFor(() => expect(screen.getByText('Step 2')).toBeDefined())
    fireEvent.click(screen.getByText('Next'))
    await waitFor(() => expect(screen.getByText('Step 3')).toBeDefined())
    fireEvent.click(screen.getByText('Next'))
    await waitFor(() => expect(screen.getByText('Step 4')).toBeDefined())
    expect(screen.queryByText('Next')).toBeNull()
    expect(screen.getByText('Done')).toBeDefined()
  })

  it('closes the dialog when Done is clicked on the last step', async () => {
    render(<TelegramChatIdHelp />)
    openDialog()
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
    fireEvent.click(screen.getByText('Next'))
    fireEvent.click(screen.getByText('Next'))
    fireEvent.click(screen.getByText('Next'))
    await waitFor(() => expect(screen.getByText('Step 4')).toBeDefined())
    fireEvent.click(screen.getByText('Done'))
    await waitFor(() => expect(screen.queryByText('Step 4')).toBeNull())
  })

  it('resets to step 1 the next time the dialog is reopened', async () => {
    render(<TelegramChatIdHelp />)
    openDialog()
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
    fireEvent.click(screen.getByText('Next'))
    await waitFor(() => expect(screen.getByText('Step 2')).toBeDefined())

    // Close via the dialog's built-in close (X) button, which calls handleOpenChange(false).
    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    await waitFor(() => expect(screen.queryByText('Step 2')).toBeNull())

    openDialog()
    await waitFor(() => expect(screen.getByText('Step 1')).toBeDefined())
  })
})
