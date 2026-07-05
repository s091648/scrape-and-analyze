import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { GuestModeProvider, useGuestMode } from "@/lib/providers/guest-mode-provider";
import { TutorialProvider, useTutorial } from "@/lib/providers/tutorial-provider";

const mockUseSession = vi.fn(() => ({ status: "unauthenticated" }));
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

const mockUsePathname = vi.fn(() => "/");
vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

vi.mock("@/components/features/tutorial/tutorial-registry", () => {
  const TUTORIAL_TOURS = [
    {
      id: "guest-onboarding",
      kind: "onboarding",
      steps: [
        { id: "welcome", route: "/", titleKey: "t1", descriptionKey: "d1" },
        { id: "articles", route: "/articles", titleKey: "t2", descriptionKey: "d2", targetId: "x" },
        { id: "graph", route: "/graph", titleKey: "t3", descriptionKey: "d3", targetId: "y" },
        { id: "cta", route: "/", titleKey: "t4", descriptionKey: "d4", targetId: "z" },
      ],
    },
    {
      id: "feature-test-spotlight",
      kind: "spotlight",
      steps: [
        {
          id: "s1",
          route: "/articles",
          titleKey: "s",
          descriptionKey: "sd",
          targetId: "chat",
        },
      ],
    },
  ];
  return {
    TUTORIAL_TOURS,
    getTour: (id: string) => TUTORIAL_TOURS.find((t) => t.id === id),
    getSpotlightTours: () => TUTORIAL_TOURS.filter((t) => t.kind === "spotlight"),
  };
});

function TestConsumer() {
  const { isGuestMode, enterGuestMode, exitGuestMode } = useGuestMode();
  const {
    isTutorialOpen,
    activeTourId,
    tutorialStep,
    openTutorial,
    closeTutorial,
    nextTutorialStep,
    prevTutorialStep,
  } = useTutorial();
  return (
    <div>
      <span data-testid="guest-status">{isGuestMode ? "guest" : "not-guest"}</span>
      <span data-testid="tutorial-status">{isTutorialOpen ? "open" : "closed"}</span>
      <span data-testid="active-tour">{activeTourId ?? "none"}</span>
      <span data-testid="tutorial-step">{tutorialStep}</span>
      <button onClick={enterGuestMode}>enter</button>
      <button onClick={exitGuestMode}>exit</button>
      <button onClick={() => openTutorial()}>open-default</button>
      <button onClick={() => openTutorial("feature-test-spotlight")}>open-spotlight</button>
      <button onClick={closeTutorial}>close-tutorial</button>
      <button onClick={nextTutorialStep}>next-step</button>
      <button onClick={prevTutorialStep}>prev-step</button>
    </div>
  );
}

function renderWithProviders() {
  return render(
    <GuestModeProvider>
      <TutorialProvider>
        <TestConsumer />
      </TutorialProvider>
    </GuestModeProvider>,
  );
}

describe("TutorialProvider — Guest Onboarding", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    mockUseSession.mockReturnValue({ status: "unauthenticated" });
    mockUsePathname.mockReturnValue("/");
  });

  it("enterGuestMode opens the guest-onboarding tour at step 0", async () => {
    renderWithProviders();
    await userEvent.click(screen.getByText("enter"));
    expect(screen.getByTestId("tutorial-status").textContent).toBe("open");
    expect(screen.getByTestId("active-tour").textContent).toBe("guest-onboarding");
    expect(screen.getByTestId("tutorial-step").textContent).toBe("0");
  });

  it("restores the tutorial as open when guest mode is restored from sessionStorage on mount (refresh)", () => {
    sessionStorage.setItem("guest_mode", "true");
    renderWithProviders();
    expect(screen.getByTestId("tutorial-status").textContent).toBe("open");
    expect(screen.getByTestId("active-tour").textContent).toBe("guest-onboarding");
  });

  it("exitGuestMode closes the tutorial and resets step/active tour", async () => {
    renderWithProviders();
    await userEvent.click(screen.getByText("enter"));
    await userEvent.click(screen.getByText("next-step"));
    await userEvent.click(screen.getByText("exit"));
    expect(screen.getByTestId("tutorial-status").textContent).toBe("closed");
    expect(screen.getByTestId("active-tour").textContent).toBe("none");
    expect(screen.getByTestId("tutorial-step").textContent).toBe("0");
  });

  it("closeTutorial does not write guest-onboarding to tutorial_seen_tours", async () => {
    renderWithProviders();
    await userEvent.click(screen.getByText("enter"));
    await userEvent.click(screen.getByText("close-tutorial"));
    expect(localStorage.getItem("tutorial_seen_tours")).toBeNull();
  });

  it("nextTutorialStep/prevTutorialStep stay within the active tour's bounds (4 steps)", async () => {
    renderWithProviders();
    await userEvent.click(screen.getByText("enter"));

    await userEvent.click(screen.getByText("prev-step"));
    expect(screen.getByTestId("tutorial-step").textContent).toBe("0");

    for (let i = 0; i < 5; i++) {
      await userEvent.click(screen.getByText("next-step"));
    }
    expect(screen.getByTestId("tutorial-step").textContent).toBe("3");
  });
});

describe("TutorialProvider — manual reopen (openTutorial)", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    mockUseSession.mockReturnValue({ status: "unauthenticated" });
    mockUsePathname.mockReturnValue("/");
  });

  it("openTutorial() with no argument opens guest-onboarding at step 0 when in guest mode", async () => {
    renderWithProviders();
    await userEvent.click(screen.getByText("enter"));
    await userEvent.click(screen.getByText("next-step"));
    await userEvent.click(screen.getByText("close-tutorial"));
    await userEvent.click(screen.getByText("open-default"));
    expect(screen.getByTestId("tutorial-status").textContent).toBe("open");
    expect(screen.getByTestId("active-tour").textContent).toBe("guest-onboarding");
    expect(screen.getByTestId("tutorial-step").textContent).toBe("0");
  });

  it("openTutorial() is a no-op when unauthenticated and not in guest mode", async () => {
    renderWithProviders();
    await userEvent.click(screen.getByText("open-default"));
    expect(screen.getByTestId("tutorial-status").textContent).toBe("closed");
  });

  it("openTutorial() opens for authenticated members", async () => {
    mockUseSession.mockReturnValue({ status: "authenticated" });
    renderWithProviders();
    await userEvent.click(screen.getByText("open-default"));
    expect(screen.getByTestId("tutorial-status").textContent).toBe("open");
  });
});

describe("TutorialProvider — Feature Spotlight auto-trigger", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    mockUseSession.mockReturnValue({ status: "unauthenticated" });
  });

  it("auto-opens an unseen spotlight tour when a guest navigates to its route (after onboarding is dismissed)", async () => {
    // Entering guest mode always wins a same-render tie with a spotlight
    // trigger (FR-001/FR-019), so this simulates the realistic sequence:
    // guest mode starts on "/", the onboarding tour is dismissed, and only
    // *then* does the guest navigate to the spotlight tour's route.
    sessionStorage.setItem("guest_mode", "true");
    mockUsePathname.mockReturnValue("/");
    const { rerender } = renderWithProviders();
    expect(screen.getByTestId("active-tour").textContent).toBe("guest-onboarding");
    await userEvent.click(screen.getByText("close-tutorial"));

    mockUsePathname.mockReturnValue("/articles");
    rerender(
      <GuestModeProvider>
        <TutorialProvider>
          <TestConsumer />
        </TutorialProvider>
      </GuestModeProvider>,
    );

    expect(screen.getByTestId("tutorial-status").textContent).toBe("open");
    expect(screen.getByTestId("active-tour").textContent).toBe("feature-test-spotlight");
  });

  it("auto-opens an unseen spotlight tour for authenticated members", async () => {
    mockUseSession.mockReturnValue({ status: "authenticated" });
    mockUsePathname.mockReturnValue("/articles");
    renderWithProviders();
    expect(screen.getByTestId("tutorial-status").textContent).toBe("open");
    expect(screen.getByTestId("active-tour").textContent).toBe("feature-test-spotlight");
  });

  it("does not auto-open for pure unauthenticated (paywall) users", () => {
    mockUsePathname.mockReturnValue("/articles");
    renderWithProviders();
    expect(screen.getByTestId("tutorial-status").textContent).toBe("closed");
  });

  it("does not auto-open on a route that doesn't match the tour's step", () => {
    sessionStorage.setItem("guest_mode", "true");
    mockUsePathname.mockReturnValue("/graph");
    renderWithProviders();
    expect(screen.getByTestId("active-tour").textContent).toBe("guest-onboarding");
  });

  it("writes the tour id to tutorial_seen_tours when a spotlight tour is closed", async () => {
    mockUseSession.mockReturnValue({ status: "authenticated" });
    mockUsePathname.mockReturnValue("/articles");
    renderWithProviders();
    expect(screen.getByTestId("active-tour").textContent).toBe("feature-test-spotlight");
    await userEvent.click(screen.getByText("close-tutorial"));
    expect(localStorage.getItem("tutorial_seen_tours")).toContain("feature-test-spotlight");
  });

  it("does not reopen a spotlight tour already marked as seen", () => {
    localStorage.setItem("tutorial_seen_tours", JSON.stringify(["feature-test-spotlight"]));
    sessionStorage.setItem("guest_mode", "true");
    mockUsePathname.mockReturnValue("/articles");
    renderWithProviders();
    expect(screen.getByTestId("active-tour").textContent).toBe("guest-onboarding");
  });

  it("does not interrupt an in-progress guest-onboarding tour", async () => {
    sessionStorage.setItem("guest_mode", "true");
    mockUsePathname.mockReturnValue("/");
    renderWithProviders();
    expect(screen.getByTestId("active-tour").textContent).toBe("guest-onboarding");

    // Simulate the onboarding tour navigating to /articles while still open —
    // the spotlight tour targeting the same route must not hijack it.
    mockUsePathname.mockReturnValue("/articles");
    await userEvent.click(screen.getByText("next-step"));
    expect(screen.getByTestId("active-tour").textContent).toBe("guest-onboarding");
  });

  it("marks an in-progress spotlight tour as seen when guest mode is exited mid-tour", async () => {
    sessionStorage.setItem("guest_mode", "true");
    mockUsePathname.mockReturnValue("/");
    const { rerender } = renderWithProviders();
    await userEvent.click(screen.getByText("close-tutorial"));

    mockUsePathname.mockReturnValue("/articles");
    rerender(
      <GuestModeProvider>
        <TutorialProvider>
          <TestConsumer />
        </TutorialProvider>
      </GuestModeProvider>,
    );
    expect(screen.getByTestId("active-tour").textContent).toBe("feature-test-spotlight");

    await userEvent.click(screen.getByText("exit"));

    expect(screen.getByTestId("tutorial-status").textContent).toBe("closed");
    expect(localStorage.getItem("tutorial_seen_tours")).toContain("feature-test-spotlight");
  });
});
