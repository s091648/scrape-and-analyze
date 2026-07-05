import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React, { useEffect } from 'react'
import { SessionProvider } from 'next-auth/react'
import { GuestModeProvider, useGuestMode } from '../lib/providers/guest-mode-provider'
import { TutorialProvider, useTutorial } from '../lib/providers/tutorial-provider'
import { TutorialOverlay } from '../components/features/tutorial/tutorial-overlay'

// Prevents state left over from a previously-viewed story in the same
// browser tab (guest mode on, or a spotlight tour already marked "seen")
// from changing which tour auto-opens.
function resetTutorialStorage() {
  if (typeof window === 'undefined') return
  window.sessionStorage.removeItem('guest_mode')
  window.localStorage.removeItem('tutorial_seen_tours')
}

function OpenAsGuest({ children }: { children: React.ReactNode }) {
  const { enterGuestMode } = useGuestMode()
  useEffect(() => {
    enterGuestMode()
  }, [enterGuestMode])
  return <>{children}</>
}

function ReopenAsMember({ children }: { children: React.ReactNode }) {
  const { openTutorial } = useTutorial()
  useEffect(() => {
    openTutorial()
  }, [openTutorial])
  return <>{children}</>
}

// Stand-in for the pin-to-chat button that the real ArticleCard renders
// (see article-card.tsx's `isFirstTutorialTarget` prop) — gives the Feature
// Spotlight Tour's first step a real element to highlight.
function FakeArticleCardWithChatPinTarget() {
  return (
    <div className="max-w-sm rounded-2xl border border-border bg-card p-4">
      <p className="text-sm font-medium mb-2">Sample Article</p>
      <button
        id="tutorial-target-chat-pin"
        type="button"
        aria-label="Pin to chat"
        className="inline-flex items-center justify-center h-6 w-6 rounded-full text-purple-400 hover:bg-purple-100"
      >
        ✦
      </button>
    </div>
  )
}

const meta: Meta<typeof TutorialOverlay> = {
  title: 'Features/Tutorial/TutorialOverlay',
  component: TutorialOverlay,
  parameters: {
    nextjs: {
      appDirectory: true,
      navigation: { pathname: '/' },
    },
  },
}
export default meta
type Story = StoryObj<typeof TutorialOverlay>

// Guest Onboarding Tour, step 1 (Welcome) — centered card, no highlight.
// Use the "Next"/"Skip" controls to step through the rest of the tour.
export const GuestOnboarding: Story = {
  decorators: [
    (Story) => {
      resetTutorialStorage()
      return (
        <SessionProvider session={null}>
          <GuestModeProvider>
            <TutorialProvider>
              <OpenAsGuest>
                <Story />
              </OpenAsGuest>
            </TutorialProvider>
          </GuestModeProvider>
        </SessionProvider>
      )
    },
  ],
}

// Same tour, reopened via NavBar's HelpCircle by an already-authenticated
// member — step 1 and the final CTA step swap to member-variant copy
// (no "Welcome to Guest Mode" / no Sign In-Register CTA).
export const ReopenedByMember: Story = {
  decorators: [
    (Story) => {
      resetTutorialStorage()
      return (
        <SessionProvider
          session={{
            user: { name: 'Jane Doe', email: 'jane@example.com' },
            expires: '2027-01-01T00:00:00.000Z',
          }}
        >
          <GuestModeProvider>
            <TutorialProvider>
              <ReopenAsMember>
                <Story />
              </ReopenAsMember>
            </TutorialProvider>
          </GuestModeProvider>
        </SessionProvider>
      )
    },
  ],
}

// Feature Spotlight Tour (a `kind: "spotlight"` registry entry, e.g.
// "feature-chat-2026-07") — auto-opens once, the first time a guest or
// member visits the tour's route, to point out a newly-shipped feature.
// Unlike the Guest Onboarding Tour, it's remembered in `tutorial_seen_tours`
// once dismissed, so it never reopens on its own after that.
export const FeatureSpotlight: Story = {
  parameters: {
    nextjs: {
      appDirectory: true,
      navigation: { pathname: '/articles' },
    },
  },
  decorators: [
    (Story) => {
      resetTutorialStorage()
      return (
        <SessionProvider
          session={{
            user: { name: 'Jane Doe', email: 'jane@example.com' },
            expires: '2027-01-01T00:00:00.000Z',
          }}
        >
          <GuestModeProvider>
            <TutorialProvider>
              <FakeArticleCardWithChatPinTarget />
              <Story />
            </TutorialProvider>
          </GuestModeProvider>
        </SessionProvider>
      )
    },
  ],
}
