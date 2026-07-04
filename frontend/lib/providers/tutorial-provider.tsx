"use client";
import { createContext, useContext, useState } from "react";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { useGuestMode } from "@/lib/providers/guest-mode-provider";
import { getTour, getSpotlightTours } from "@/components/features/tutorial/tutorial-registry";

const SEEN_TOURS_KEY = "tutorial_seen_tours";
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

export function TutorialProvider({ children }: { children: React.ReactNode }) {
  const { isGuestMode } = useGuestMode();
  const { status } = useSession();
  const pathname = usePathname();

  const [isTutorialOpen, setIsTutorialOpen] = useState(false);
  const [activeTourId, setActiveTourId] = useState<string | null>(null);
  const [tutorialStep, setTutorialStep] = useState(0);

  const activeTour = activeTourId ? getTour(activeTourId) : undefined;
  const stepCount = activeTour?.steps.length ?? 1;

  function openTutorial(tourId: string = DEFAULT_TOUR_ID) {
    if (status === "unauthenticated" && !isGuestMode) return;
    setActiveTourId(tourId);
    setIsTutorialOpen(true);
    setTutorialStep(0);
  }

  function closeTutorial() {
    if (activeTourId && getTour(activeTourId)?.kind === "spotlight") {
      markTourSeen(activeTourId);
    }
    setIsTutorialOpen(false);
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

  // Guest Onboarding Tour: unconditional auto-open whenever guest mode turns
  // on (including on first render, e.g. after a page refresh while already in
  // guest mode), and auto-close when guest mode turns off (FR-001, FR-011).
  const [prevIsGuestMode, setPrevIsGuestMode] = useState(false);
  if (isGuestMode !== prevIsGuestMode) {
    setPrevIsGuestMode(isGuestMode);
    if (isGuestMode) {
      setActiveTourId(DEFAULT_TOUR_ID);
      setIsTutorialOpen(true);
      setTutorialStep(0);
      effectiveIsTutorialOpen = true;
    } else {
      setIsTutorialOpen(false);
      setActiveTourId(null);
      setTutorialStep(0);
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
      const match = getSpotlightTours().find(
        (tour) => tour.steps[0]?.route === pathname && !seen.includes(tour.id),
      );
      if (match) {
        setActiveTourId(match.id);
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
