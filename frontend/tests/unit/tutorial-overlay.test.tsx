import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TutorialOverlay } from "@/components/features/tutorial/tutorial-overlay";

const {
  mockPush,
  mockUsePathname,
  mockUseTutorial,
  mockUseI18n,
  mockUseTutorialTarget,
  mockUseIsMobile,
  mockUseGuestMode,
} = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockUsePathname: vi.fn(() => "/"),
  mockUseTutorial: vi.fn(),
  mockUseI18n: vi.fn(),
  mockUseTutorialTarget: vi.fn(),
  mockUseIsMobile: vi.fn(() => false),
  mockUseGuestMode: vi.fn(() => ({ isGuestMode: true })),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockUsePathname(),
}));

vi.mock("@/lib/providers", () => ({
  useTutorial: () => mockUseTutorial(),
  useI18n: () => mockUseI18n(),
  useGuestMode: () => mockUseGuestMode(),
}));

vi.mock("@/components/features/tutorial/use-tutorial-target", () => ({
  useTutorialTarget: (targetId: string | undefined) => mockUseTutorialTarget(targetId),
}));

vi.mock("@/components/features/tutorial/use-is-mobile", () => ({
  useIsMobile: () => mockUseIsMobile(),
}));

vi.mock("@/components/features/tutorial/tutorial-registry", () => {
  const TUTORIAL_TOURS = [
    {
      id: "guest-onboarding",
      kind: "onboarding",
      steps: [
        {
          id: "welcome",
          route: "/",
          titleKey: "tutorial.step1.title",
          descriptionKey: "tutorial.step1.description",
          titleKeyMember: "tutorial.step1Member.title",
          descriptionKeyMember: "tutorial.step1Member.description",
        },
        { id: "articles", route: "/articles", titleKey: "tutorial.step2.title", descriptionKey: "tutorial.step2.description", targetId: "tutorial-target-articles" },
        { id: "graph", route: "/graph", titleKey: "tutorial.step3.title", descriptionKey: "tutorial.step3.description", targetId: "tutorial-target-graph" },
        { id: "cta", route: "/", titleKey: "tutorial.step4.title", descriptionKey: "tutorial.step4.description", targetId: "tutorial-target-login", isCta: true },
      ],
    },
    {
      id: "feature-test-spotlight",
      kind: "spotlight",
      steps: [
        { id: "spot", route: "/articles", titleKey: "tutorial.chatPin.title", descriptionKey: "tutorial.chatPin.description", targetId: "tutorial-target-chat-pin" },
      ],
    },
  ];
  return { getTour: (id: string) => TUTORIAL_TOURS.find((t) => t.id === id) };
});

const en: Record<string, any> = {
  "tutorial.stepOf": (p: any) => `Step ${p.current} of ${p.total}`,
  "tutorial.skip": "Skip",
  "tutorial.back": "Back",
  "tutorial.next": "Next",
  "tutorial.signIn": "Sign In",
  "tutorial.register": "Register",
  "tutorial.done": "Done",
  "tutorial.chatPin.title": "Pin Articles for Context",
  "tutorial.chatPin.description": "Click the sparkles icon to pin an article.",
  "tutorial.step1.title": "Welcome to Guest Mode",
  "tutorial.step1.description": "You're browsing as a guest.",
  "tutorial.step1Member.title": "Welcome Back",
  "tutorial.step1Member.description": "Here's a quick refresher.",
  "tutorial.step2.title": "Browse Articles",
  "tutorial.step2.description": "The home page shows the latest AI research articles.",
  "tutorial.step3.title": "Explore the Knowledge Graph",
  "tutorial.step3.description": "The Graph page visualizes connections.",
  "tutorial.step4.title": "Get Full Access",
  "tutorial.step4.description": "Sign in or create a free account.",
};

const zhTW: Record<string, any> = {
  "tutorial.stepOf": (p: any) => `第 ${p.current} 步，共 ${p.total} 步`,
  "tutorial.step1.title": "歡迎使用訪客模式",
  "tutorial.step1.description": "您正以訪客身份瀏覽。",
};

function makeT(dict: Record<string, any>) {
  return (key: string, params?: Record<string, string | number>) => {
    const entry = dict[key];
    if (typeof entry === "function") return entry(params);
    return entry ?? key;
  };
}

function baseTutorialCtx(overrides: Partial<ReturnType<typeof defaultTutorialCtx>> = {}) {
  return { ...defaultTutorialCtx(), ...overrides };
}

function defaultTutorialCtx() {
  return {
    isTutorialOpen: true,
    activeTourId: "guest-onboarding",
    tutorialStep: 0,
    closeTutorial: vi.fn(),
    nextTutorialStep: vi.fn(),
    prevTutorialStep: vi.fn(),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseI18n.mockReturnValue({ t: makeT(en), locale: "en" });
  mockUsePathname.mockReturnValue("/");
  mockUseIsMobile.mockReturnValue(false);
  mockUseTutorialTarget.mockReturnValue(null);
  mockUseGuestMode.mockReturnValue({ isGuestMode: true });
});

describe("TutorialOverlay", () => {
  it("renders null when isTutorialOpen is false", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ isTutorialOpen: false }));
    const { container } = render(<TutorialOverlay />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders centered card (no highlight) for the Welcome step", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 0 }));
    mockUseTutorialTarget.mockReturnValue(null);
    render(<TutorialOverlay />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Welcome to Guest Mode")).toBeInTheDocument();
    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
  });

  it("renders spotlight mode with a highlight box when a target rect is found", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 1 }));
    mockUsePathname.mockReturnValue("/articles");
    mockUseTutorialTarget.mockReturnValue({
      top: 10,
      left: 20,
      width: 100,
      height: 30,
      bottom: 40,
      right: 120,
    } as DOMRect);
    render(<TutorialOverlay />);
    expect(screen.getByText("Browse Articles")).toBeInTheDocument();
    // Spotlight mode renders a Popover, not a Dialog — no dialog-content slot,
    // and the highlight/backdrop layers are present.
    expect(document.querySelector('[data-slot="dialog-content"]')).not.toBeInTheDocument();
    expect(document.querySelector('[data-slot="popover-content"]')).toBeInTheDocument();
    expect(screen.getByTestId("tutorial-highlight")).toBeInTheDocument();
    expect(screen.getByTestId("tutorial-backdrop")).toBeInTheDocument();
    expect(screen.getAllByTestId("tutorial-dot")).toHaveLength(4);
  });

  it("falls back to centered card on mobile even when a target rect is found", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 1 }));
    mockUsePathname.mockReturnValue("/articles");
    mockUseIsMobile.mockReturnValue(true);
    mockUseTutorialTarget.mockReturnValue({
      top: 10,
      left: 20,
      width: 100,
      height: 30,
      bottom: 40,
      right: 120,
    } as DOMRect);
    render(<TutorialOverlay />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("hides the Back button on step 0", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 0 }));
    render(<TutorialOverlay />);
    expect(screen.queryByText("Back")).not.toBeInTheDocument();
  });

  it("calls nextTutorialStep when Next is clicked", async () => {
    const nextTutorialStep = vi.fn();
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 0, nextTutorialStep }));
    render(<TutorialOverlay />);
    await userEvent.click(screen.getByText("Next"));
    expect(nextTutorialStep).toHaveBeenCalledOnce();
  });

  it("calls prevTutorialStep when Back is clicked on step 1", async () => {
    const prevTutorialStep = vi.fn();
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 1, prevTutorialStep }));
    render(<TutorialOverlay />);
    await userEvent.click(screen.getByText("Back"));
    expect(prevTutorialStep).toHaveBeenCalledOnce();
  });

  it("calls closeTutorial when Skip is clicked", async () => {
    const closeTutorial = vi.fn();
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 0, closeTutorial }));
    render(<TutorialOverlay />);
    await userEvent.click(screen.getByText("Skip"));
    expect(closeTutorial).toHaveBeenCalledOnce();
  });

  it("does not navigate on the initial open — the caller (enterGuestMode/HelpCircle) is responsible for that", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 1 }));
    mockUsePathname.mockReturnValue("/");
    render(<TutorialOverlay />);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("navigates to the new step's route when the step changes while already open", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 0 }));
    mockUsePathname.mockReturnValue("/");
    const { rerender } = render(<TutorialOverlay />);
    expect(mockPush).not.toHaveBeenCalled();

    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 1 }));
    rerender(<TutorialOverlay />);
    expect(mockPush).toHaveBeenCalledWith("/articles");
  });

  it("does not navigate again once the route already matches the new step", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 1 }));
    mockUsePathname.mockReturnValue("/articles");
    const { rerender } = render(<TutorialOverlay />);
    expect(mockPush).not.toHaveBeenCalled();

    // pathname still reads the OLD route here — mirrors reality, where the
    // URL only updates once router.push's navigation actually resolves.
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 2 }));
    rerender(<TutorialOverlay />);
    expect(mockPush).toHaveBeenCalledWith("/graph");
    expect(mockPush).toHaveBeenCalledTimes(1);

    // Now pathname catches up to reflect the completed navigation — no
    // redundant second push should fire.
    mockUsePathname.mockReturnValue("/graph");
    rerender(<TutorialOverlay />);
    expect(mockPush).toHaveBeenCalledTimes(1);
  });

  it("renders all 4 steps in order: welcome, articles, graph, cta", () => {
    const titles = [
      "Welcome to Guest Mode",
      "Browse Articles",
      "Explore the Knowledge Graph",
      "Get Full Access",
    ];
    titles.forEach((title, index) => {
      mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: index }));
      const { unmount } = render(<TutorialOverlay />);
      expect(screen.getByText(title)).toBeInTheDocument();
      expect(screen.getByText(`Step ${index + 1} of 4`)).toBeInTheDocument();
      unmount();
    });
  });

  it("shows Sign In and Register CTAs (not Skip/Next) on the guest-onboarding last step (isCta)", () => {
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 3 }));
    render(<TutorialOverlay />);
    expect(screen.getByText("Sign In")).toBeInTheDocument();
    expect(screen.getByText("Register")).toBeInTheDocument();
    expect(screen.queryByText("Skip")).not.toBeInTheDocument();
    expect(screen.queryByText("Next")).not.toBeInTheDocument();
  });

  it("shows a Done button (not Sign In/Register) on a non-CTA tour's last step", async () => {
    const closeTutorial = vi.fn();
    mockUseTutorial.mockReturnValue(
      baseTutorialCtx({ activeTourId: "feature-test-spotlight", tutorialStep: 0, closeTutorial }),
    );
    mockUsePathname.mockReturnValue("/articles");
    mockUseTutorialTarget.mockReturnValue({
      top: 10,
      left: 20,
      width: 40,
      height: 20,
      bottom: 30,
      right: 60,
    } as DOMRect);
    render(<TutorialOverlay />);
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.queryByText("Sign In")).not.toBeInTheDocument();
    expect(screen.queryByText("Register")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText("Done"));
    expect(closeTutorial).toHaveBeenCalledOnce();
  });

  it("navigates to /login and closes the tutorial when Sign In is clicked", async () => {
    const closeTutorial = vi.fn();
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 3, closeTutorial }));
    render(<TutorialOverlay />);
    await userEvent.click(screen.getByText("Sign In"));
    expect(mockPush).toHaveBeenCalledWith("/login");
    expect(closeTutorial).toHaveBeenCalledOnce();
  });

  it("navigates to /register and closes the tutorial when Register is clicked", async () => {
    const closeTutorial = vi.fn();
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 3, closeTutorial }));
    render(<TutorialOverlay />);
    await userEvent.click(screen.getByText("Register"));
    expect(mockPush).toHaveBeenCalledWith("/register");
    expect(closeTutorial).toHaveBeenCalledOnce();
  });

  it("renders zh-TW copy when locale is zh-TW", () => {
    mockUseI18n.mockReturnValue({ t: makeT(zhTW), locale: "zh-TW" });
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 0 }));
    render(<TutorialOverlay />);
    expect(screen.getByText("歡迎使用訪客模式")).toBeInTheDocument();
    expect(screen.getByText("第 1 步，共 4 步")).toBeInTheDocument();
  });

  it("renders English copy when locale is en", () => {
    mockUseI18n.mockReturnValue({ t: makeT(en), locale: "en" });
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 0 }));
    render(<TutorialOverlay />);
    expect(screen.getByText("Welcome to Guest Mode")).toBeInTheDocument();
  });

  it("shows the member-variant welcome copy when reopened by an authenticated (non-guest) member", () => {
    mockUseGuestMode.mockReturnValue({ isGuestMode: false });
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 0 }));
    render(<TutorialOverlay />);
    expect(screen.getByText("Welcome Back")).toBeInTheDocument();
    expect(screen.queryByText("Welcome to Guest Mode")).not.toBeInTheDocument();
  });

  it("shows a Done button instead of Sign In/Register on the CTA step when reopened by a member", () => {
    mockUseGuestMode.mockReturnValue({ isGuestMode: false });
    mockUseTutorial.mockReturnValue(baseTutorialCtx({ tutorialStep: 3 }));
    render(<TutorialOverlay />);
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.queryByText("Sign In")).not.toBeInTheDocument();
    expect(screen.queryByText("Register")).not.toBeInTheDocument();
  });
});
