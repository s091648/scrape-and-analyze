import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

const mockUsePathname = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

vi.mock("next-auth/react", () => ({
  useSession: vi.fn().mockReturnValue({ data: null, status: "unauthenticated" }),
}));

vi.mock("@/components/features/navigation/nav-bar", () => ({
  NavBar: () => <nav data-testid="navbar">NavBar</nav>,
}));

vi.mock("@/components/features/tutorial/tutorial-overlay", () => ({
  TutorialOverlay: () => <div data-testid="tutorial-overlay" />,
}));

vi.mock("@/components/common/error-boundary", () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/features/chat/FloatingChatbotWrapper", () => ({
  FloatingChatbotWrapper: () => <div data-testid="floating-chatbot" />,
}));

describe("LayoutShell", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders NavBar for root path", async () => {
    mockUsePathname.mockReturnValue("/");
    const { LayoutShell } = await import("@/app/layout-shell");
    render(
      <LayoutShell>
        <div>content</div>
      </LayoutShell>,
    );
    expect(screen.getByTestId("navbar")).toBeInTheDocument();
  });

  it("mounts TutorialOverlay", async () => {
    mockUsePathname.mockReturnValue("/");
    const { LayoutShell } = await import("@/app/layout-shell");
    render(
      <LayoutShell>
        <div>content</div>
      </LayoutShell>,
    );
    expect(screen.getByTestId("tutorial-overlay")).toBeInTheDocument();
  });

  it("renders NavBar for /graph path", async () => {
    mockUsePathname.mockReturnValue("/graph");
    const { LayoutShell } = await import("@/app/layout-shell");
    render(
      <LayoutShell>
        <div>content</div>
      </LayoutShell>,
    );
    expect(screen.getByTestId("navbar")).toBeInTheDocument();
  });

  it("hides NavBar for /articles/* path", async () => {
    mockUsePathname.mockReturnValue("/articles/abc-123");
    const { LayoutShell } = await import("@/app/layout-shell");
    render(
      <LayoutShell>
        <div>content</div>
      </LayoutShell>,
    );
    expect(screen.queryByTestId("navbar")).not.toBeInTheDocument();
  });

  it("renders children on all paths", async () => {
    mockUsePathname.mockReturnValue("/");
    const { LayoutShell } = await import("@/app/layout-shell");
    render(
      <LayoutShell>
        <div data-testid="child">hello</div>
      </LayoutShell>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("applies pt-24 class to main on normal paths", async () => {
    mockUsePathname.mockReturnValue("/");
    const { LayoutShell } = await import("@/app/layout-shell");
    const { container } = render(
      <LayoutShell>
        <div>content</div>
      </LayoutShell>,
    );
    expect(container.querySelector("main")?.className).toContain("pt-24");
  });

  it("does not apply pt-24 class to main on /articles/* paths", async () => {
    mockUsePathname.mockReturnValue("/articles/some-uuid");
    const { LayoutShell } = await import("@/app/layout-shell");
    const { container } = render(
      <LayoutShell>
        <div>content</div>
      </LayoutShell>,
    );
    expect(container.querySelector("main")?.className).not.toContain("pt-24");
  });
});
