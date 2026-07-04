import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NavBar } from "@/components/features/navigation/nav-bar";

const { mockSignOut, mockUseSession, mockPush } = vi.hoisted(() => ({
  mockSignOut: vi.fn(),
  mockUseSession: vi.fn(),
  mockPush: vi.fn(),
}));
vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
  signOut: mockSignOut,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: mockPush }),
}));

const { mockUseTopic, mockUseI18n, mockUseTheme, mockUseGuestMode, mockUseTutorial } = vi.hoisted(
  () => ({
    mockUseTopic: vi.fn(),
    mockUseI18n: vi.fn(),
    mockUseTheme: vi.fn(),
    mockUseGuestMode: vi.fn(),
    mockUseTutorial: vi.fn(),
  }),
);
const mockSetSelectedTopicId = vi.fn();
const mockSetLocale = vi.fn();
const mockCycleMode = vi.fn();
const mockOpenTutorial = vi.fn();
vi.mock("@/lib/providers", () => ({
  useTopic: () => mockUseTopic(),
  useI18n: () => mockUseI18n(),
  useTheme: () => mockUseTheme(),
  useGuestMode: () => mockUseGuestMode(),
  useTutorial: () => mockUseTutorial(),
}));

vi.mock("@/lib/api/auth", () => ({
  fetchMe: vi.fn().mockResolvedValue(null),
}));

vi.mock("@/components/features/navigation/release-notes-popover", () => ({
  ReleaseNotesPopover: () => <div data-testid="release-notes" />,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const defaultTopics = [
  { id: "t1", display_name: "AI", color_hex: null, sort_order: 0, tag_mode: "unsupervised" },
  { id: "t2", display_name: "ML", color_hex: "#f00", sort_order: 1, tag_mode: "unsupervised" },
];

const defaultTopicCtx = {
  topics: defaultTopics,
  selectedTopic: defaultTopics[0],
  setSelectedTopicId: mockSetSelectedTopicId,
  isLoading: false,
};

const defaultI18nCtx = {
  locale: "en",
  setLocale: mockSetLocale,
  availableLanguages: [
    { code: "en", name: "English", native_name: "English" },
    { code: "zh-TW", name: "Traditional Chinese", native_name: "繁體中文" },
  ],
  t: (key: string) => key,
  isLoading: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockUseTopic.mockReturnValue(defaultTopicCtx);
  mockUseI18n.mockReturnValue(defaultI18nCtx);
  mockUseTheme.mockReturnValue({
    mode: "auto",
    theme: "light",
    cycleMode: mockCycleMode,
    setMode: vi.fn(),
  });
  mockUseGuestMode.mockReturnValue({ isGuestMode: false });
  mockUseTutorial.mockReturnValue({ openTutorial: mockOpenTutorial });
});

describe("NavBar", () => {
  it("renders the brand link", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    expect(screen.getByText("Scrape Analyzer")).toBeInTheDocument();
  });

  it("shows login button when not authenticated", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    expect(screen.getByText("nav.login")).toBeInTheDocument();
  });

  it("does not show logout or username when no session", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    expect(screen.queryByText("nav.logout")).not.toBeInTheDocument();
  });

  it("shows username and logout button when authenticated", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice Smith" }, accessToken: "tok" },
    });
    render(<NavBar />);
    expect(screen.getByText("Alice Smith")).toBeInTheDocument();
    expect(screen.getByText("nav.logout")).toBeInTheDocument();
  });

  it("shows settings link when authenticated", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice" }, accessToken: "tok" },
    });
    render(<NavBar />);
    // Settings link has no text/aria-label — query by href
    const settingsLink = document.querySelector('a[href="/settings"]');
    expect(settingsLink).toBeTruthy();
  });

  it("calls signOut when logout button is clicked", () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Alice" }, accessToken: "tok" },
    });
    render(<NavBar />);
    fireEvent.click(screen.getByText("nav.logout"));
    expect(mockSignOut).toHaveBeenCalled();
  });

  it("renders user initials when authenticated and no icon", async () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: "Bob Jones" }, accessToken: "tok" },
    });
    render(<NavBar />);
    await waitFor(() => expect(screen.getByText("BJ")).toBeInTheDocument());
  });

  it("shows ? initials when user name is null", async () => {
    mockUseSession.mockReturnValue({
      data: { user: { name: null, email: null }, accessToken: "tok" },
    });
    render(<NavBar />);
    await waitFor(() => expect(screen.getByText("?")).toBeInTheDocument());
  });

  it("renders selected topic name in topic dropdown", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    // 'AI' appears in both the trigger button and the dropdown list item
    expect(screen.getAllByText("AI").length).toBeGreaterThan(0);
  });

  it("renders current language in language selector", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    expect(screen.getByText("English")).toBeInTheDocument();
  });

  it("opens language dropdown on button click", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    const langButton = screen
      .getAllByRole("button")
      .find((b) => b.textContent?.includes("English"))!;
    fireEvent.click(langButton);
    expect(screen.getByText("繁體中文")).toBeInTheDocument();
  });

  it("calls setLocale and closes dropdown when a language is selected", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    const langButton = screen
      .getAllByRole("button")
      .find((b) => b.textContent?.includes("English"))!;
    fireEvent.click(langButton);
    fireEvent.click(screen.getByText("繁體中文"));
    expect(mockSetLocale).toHaveBeenCalledWith("zh-TW");
  });

  it("renders navigation links", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    expect(screen.getByText("nav.articles")).toBeInTheDocument();
    expect(screen.getByText("nav.knowledgeGraph")).toBeInTheDocument();
    expect(screen.getByText("tags.title")).toBeInTheDocument();
  });

  it("renders release notes popover", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    expect(screen.getByTestId("release-notes")).toBeInTheDocument();
  });

  it("renders topic dropdown buttons for all topics", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    expect(screen.getByText("ML")).toBeInTheDocument();
  });

  it("calls setSelectedTopicId when a topic is clicked", () => {
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    fireEvent.click(screen.getByText("ML"));
    expect(mockSetSelectedTopicId).toHaveBeenCalledWith("t2");
  });

  it('shows "Select topic" when no topic is selected', () => {
    mockUseTopic.mockReturnValue({ ...defaultTopicCtx, selectedTopic: null });
    mockUseSession.mockReturnValue({ data: null });
    render(<NavBar />);
    expect(screen.getByText("Select topic")).toBeInTheDocument();
  });
});

describe("NavBar — theme toggle", () => {
  beforeEach(() => {
    mockUseSession.mockReturnValue({ data: null });
  });

  it("renders theme toggle button with aria-label matching current mode", () => {
    mockUseTheme.mockReturnValue({
      mode: "auto",
      theme: "light",
      cycleMode: mockCycleMode,
      setMode: vi.fn(),
    });
    render(<NavBar />);
    expect(screen.getByRole("button", { name: "Theme: Auto" })).toBeInTheDocument();
  });

  it('aria-label is "Theme: Light" when mode is light', () => {
    mockUseTheme.mockReturnValue({
      mode: "light",
      theme: "light",
      cycleMode: mockCycleMode,
      setMode: vi.fn(),
    });
    render(<NavBar />);
    expect(screen.getByRole("button", { name: "Theme: Light" })).toBeInTheDocument();
  });

  it('aria-label is "Theme: Dark" when mode is dark', () => {
    mockUseTheme.mockReturnValue({
      mode: "dark",
      theme: "dark",
      cycleMode: mockCycleMode,
      setMode: vi.fn(),
    });
    render(<NavBar />);
    expect(screen.getByRole("button", { name: "Theme: Dark" })).toBeInTheDocument();
  });

  it("calls cycleMode when theme toggle is clicked", () => {
    mockUseTheme.mockReturnValue({
      mode: "auto",
      theme: "light",
      cycleMode: mockCycleMode,
      setMode: vi.fn(),
    });
    render(<NavBar />);
    fireEvent.click(screen.getByRole("button", { name: "Theme: Auto" }));
    expect(mockCycleMode).toHaveBeenCalledOnce();
  });
});

describe("NavBar — tutorial reopen icon", () => {
  beforeEach(() => {
    mockUseTutorial.mockReturnValue({ openTutorial: mockOpenTutorial });
  });

  it("is hidden for pure unauthenticated (paywall) users", () => {
    mockUseSession.mockReturnValue({ data: null });
    mockUseGuestMode.mockReturnValue({ isGuestMode: false });
    render(<NavBar />);
    expect(screen.queryByLabelText("tutorial.reopenLabel")).not.toBeInTheDocument();
  });

  it("is visible in guest mode and calls openTutorial() + navigates home when clicked", () => {
    mockUseSession.mockReturnValue({ data: null });
    mockUseGuestMode.mockReturnValue({ isGuestMode: true });
    render(<NavBar />);
    const helpButton = screen.getByLabelText("tutorial.reopenLabel");
    fireEvent.click(helpButton);
    expect(mockOpenTutorial).toHaveBeenCalledOnce();
    expect(mockOpenTutorial).toHaveBeenCalledWith();
    expect(mockPush).toHaveBeenCalledWith("/");
  });

  it("is visible for authenticated members", () => {
    mockUseSession.mockReturnValue({ data: { user: { name: "Alice" }, accessToken: "tok" } });
    mockUseGuestMode.mockReturnValue({ isGuestMode: false });
    render(<NavBar />);
    expect(screen.getByLabelText("tutorial.reopenLabel")).toBeInTheDocument();
  });

  it("exposes id attributes on the Articles, Graph, Tags, language, theme, GitHub, docs, and login nav targets for tutorial highlighting", () => {
    mockUseSession.mockReturnValue({ data: null });
    mockUseGuestMode.mockReturnValue({ isGuestMode: false });
    render(<NavBar />);
    expect(document.getElementById("tutorial-target-articles")).toBeTruthy();
    expect(document.getElementById("tutorial-target-graph")).toBeTruthy();
    expect(document.getElementById("tutorial-target-tags")).toBeTruthy();
    expect(document.getElementById("tutorial-target-language")).toBeTruthy();
    expect(document.getElementById("tutorial-target-theme")).toBeTruthy();
    expect(document.getElementById("tutorial-target-github")).toBeTruthy();
    expect(document.getElementById("tutorial-target-docs")).toBeTruthy();
    expect(document.getElementById("tutorial-target-login")).toBeTruthy();
  });
});
