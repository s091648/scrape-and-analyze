"use client";
import { createContext, useContext, useState } from "react";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { useGuestMode } from "@/lib/providers/guest-mode-provider";
import { getTour, getSpotlightTours } from "@/components/features/tutorial/tutorial-registry";

const SEEN_TOURS_KEY = "tutorial_seen_tours";
// sessionStorage (not localStorage): the onboarding tour should reappear on a
// fresh guest-mode entry (new tab, or exit+re-enter) but not on every refresh
// within the same tab session once dismissed.
const ONBOARDING_DISMISSED_KEY = "tutorial_onboarding_dismissed";
const DEFAULT_TOUR_ID = "guest-onboarding";

interface TutorialContextType {
  isTutorialOpen: boolean;
  activeTourId: string | null;
  tutorialStep: number;
  openTutorial: (tourId?: string) => void;
  closeTutorial: () => void;
  nextTutorialStep: () => void;
  prevTutorialStep: () => void;
}

const TutorialContext = createContext<TutorialContextType>({
  isTutorialOpen: false,
  activeTourId: null,
  tutorialStep: 0,
  openTutorial: () => {},
  closeTutorial: () => {},
  nextTutorialStep: () => {},
  prevTutorialStep: () => {},
});

function readSeenTours(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(SEEN_TOURS_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function markTourSeen(tourId: string) {
  const seen = readSeenTours();
  if (!seen.includes(tourId)) {
    localStorage.setItem(SEEN_TOURS_KEY, JSON.stringify([...seen, tourId]));
  }
}

function isOnboardingDismissed(): boolean {
  if (typeof window === "undefined") return false;
  return sessionStorage.getItem(ONBOARDING_DISMISSED_KEY) === "true";
}

function markOnboardingDismissed() {
  sessionStorage.setItem(ONBOARDING_DISMISSED_KEY, "true");
}

export function TutorialProvider({ children }: { children: React.ReactNode }) {
  const { isGuestMode } = useGuestMode();
  const { status } = useSession();
  const pathname = usePathname();

  const [isTutorialOpen, setIsTutorialOpen] = useState(false);
  const [activeTourId, setActiveTourId] = useState<string | null>(null);
  const [tutorialStep, setTutorialStep] = useState(0);
  // Remaining auto-triggered spotlight tours still queued for the current
  // page, so closing one immediately chains into the next instead of
  // requiring a fresh page visit to surface it (FR: multiple new-feature
  // tours on the same page should all play back-to-back).
  const [spotlightQueue, setSpotlightQueue] = useState<string[]>([]);

  const activeTour = activeTourId ? getTour(activeTourId) : undefined;
  const stepCount = activeTour?.steps.length ?? 1;

  function openTutorial(tourId: string = DEFAULT_TOUR_ID) {
    if (status === "unauthenticated" && !isGuestMode) return;
    setSpotlightQueue([]);
    setActiveTourId(tourId);
    setIsTutorialOpen(true);
    setTutorialStep(0);
  }

  function closeTutorial() {
    const closedTourKind = activeTourId ? getTour(activeTourId)?.kind : undefined;
    if (activeTourId && closedTourKind === "spotlight") {
      markTourSeen(activeTourId);
    } else if (activeTourId && closedTourKind === "onboarding") {
      markOnboardingDismissed();
    }
    const [nextTourId, ...rest] = spotlightQueue;
    setSpotlightQueue(rest);
    if (nextTourId) {
      setActiveTourId(nextTourId);
      setTutorialStep(0);
    } else {
      setIsTutorialOpen(false);
    }
  }

  function nextTutorialStep() {
    setTutorialStep((step) => Math.min(step + 1, stepCount - 1));
  }

  function prevTutorialStep() {
    setTutorialStep((step) => Math.max(step - 1, 0));
  }

  // Both blocks below adjust state during render (not in effects) per React's
  // "adjusting state when a prop changes" pattern, each tracked via a mirrored
  // previous-value state. `effectiveIsTutorialOpen` tracks what isTutorialOpen
  // will be *after* this render's adjustments (the `isTutorialOpen` state
  // variable itself won't reflect a same-render setState until the next
  // render), so the two blocks stay mutually exclusive even if both trigger
  // in the same render (FR-019) — e.g. enterGuestMode() and router.push('/')
  // both firing together in login-page-content.tsx.
  let effectiveIsTutorialOpen = isTutorialOpen;

  // Guest Onboarding Tour: auto-open whenever guest mode turns on (including
  // on first render, e.g. after a page refresh while already in guest mode),
  // unless it was already dismissed this tab session; auto-close when guest
  // mode turns off (FR-001, FR-011).
  const [prevIsGuestMode, setPrevIsGuestMode] = useState(false);
  if (isGuestMode !== prevIsGuestMode) {
    setPrevIsGuestMode(isGuestMode);
    if (isGuestMode) {
      setSpotlightQueue([]);
      if (!isOnboardingDismissed()) {
        setActiveTourId(DEFAULT_TOUR_ID);
        setIsTutorialOpen(true);
        setTutorialStep(0);
        effectiveIsTutorialOpen = true;
      }
    } else {
      if (activeTourId && getTour(activeTourId)?.kind === "spotlight") {
        markTourSeen(activeTourId);
      }
      // A fresh guest-mode entry (new tab, or exit+re-enter) is a new
      // onboarding opportunity, so clear this tab session's dismissal.
      sessionStorage.removeItem(ONBOARDING_DISMISSED_KEY);
      setIsTutorialOpen(false);
      setActiveTourId(null);
      setTutorialStep(0);
      setSpotlightQueue([]);
      effectiveIsTutorialOpen = false;
    }
  }

  // Feature Spotlight Tours: auto-open the first unseen spotlight tour whose
  // first step's route matches the current page. Never force-navigates, and
  // never interrupts a tour already in progress (FR-017, FR-019).
  const spotlightTriggerKey = `${pathname}|${isGuestMode}|${status}`;
  // Sentinel `null` initial value (not `spotlightTriggerKey`) so the check
  // also runs on the very first render, not just on subsequent changes.
  const [prevSpotlightTriggerKey, setPrevSpotlightTriggerKey] = useState<string | null>(null);
  if (spotlightTriggerKey !== prevSpotlightTriggerKey) {
    setPrevSpotlightTriggerKey(spotlightTriggerKey);
    if (!effectiveIsTutorialOpen && (isGuestMode || status === "authenticated")) {
      const seen = readSeenTours();
      const matches = getSpotlightTours().filter(
        (tour) => tour.steps[0]?.route === pathname && !seen.includes(tour.id),
      );
      if (matches.length > 0) {
        const [first, ...rest] = matches;
        setSpotlightQueue(rest.map((tour) => tour.id));
        setActiveTourId(first.id);
        setIsTutorialOpen(true);
        setTutorialStep(0);
      }
    }
  }

  return (
    <TutorialContext.Provider
      value={{
        isTutorialOpen,
        activeTourId,
        tutorialStep,
        openTutorial,
        closeTutorial,
        nextTutorialStep,
        prevTutorialStep,
      }}
    >
      {children}
    </TutorialContext.Provider>
  );
}

export function useTutorial() {
  return useContext(TutorialContext);
}
