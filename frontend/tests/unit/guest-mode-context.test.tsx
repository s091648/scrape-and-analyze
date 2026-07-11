import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { GuestModeProvider, useGuestMode } from "@/lib/providers/guest-mode-provider";

const mockUseSession = vi.fn(() => ({ status: "unauthenticated" }));

vi.mock("next-auth/react", () => ({
  useSession: () => mockUseSession(),
}));

function TestConsumer() {
  const { isGuestMode, enterGuestMode, exitGuestMode } = useGuestMode();
  return (
    <div>
      <span data-testid="status">{isGuestMode ? "guest" : "not-guest"}</span>
      <button onClick={enterGuestMode}>enter</button>
      <button onClick={exitGuestMode}>exit</button>
    </div>
  );
}

function renderWithProvider() {
  return render(
    <GuestModeProvider>
      <TestConsumer />
    </GuestModeProvider>,
  );
}

describe("GuestModeContext", () => {
  beforeEach(() => {
    sessionStorage.clear();
    mockUseSession.mockReturnValue({ status: "unauthenticated" });
  });

  it("is not in guest mode by default", () => {
    renderWithProvider();
    expect(screen.getByTestId("status").textContent).toBe("not-guest");
  });

  it("enterGuestMode sets isGuestMode and persists to sessionStorage", async () => {
    renderWithProvider();
    await userEvent.click(screen.getByText("enter"));
    expect(screen.getByTestId("status").textContent).toBe("guest");
    expect(sessionStorage.getItem("guest_mode")).toBe("true");
  });

  it("exitGuestMode clears isGuestMode and removes from sessionStorage", async () => {
    renderWithProvider();
    await userEvent.click(screen.getByText("enter"));
    await userEvent.click(screen.getByText("exit"));
    expect(screen.getByTestId("status").textContent).toBe("not-guest");
    expect(sessionStorage.getItem("guest_mode")).toBeNull();
  });

  it("restores guest mode from sessionStorage on mount", () => {
    sessionStorage.setItem("guest_mode", "true");
    renderWithProvider();
    expect(screen.getByTestId("status").textContent).toBe("guest");
  });

  it("auto-exits guest mode when status becomes authenticated", async () => {
    sessionStorage.setItem("guest_mode", "true");
    const { rerender } = renderWithProvider();
    expect(screen.getByTestId("status").textContent).toBe("guest");

    mockUseSession.mockReturnValue({ status: "authenticated" });

    await act(async () => {
      rerender(
        <GuestModeProvider>
          <TestConsumer />
        </GuestModeProvider>,
      );
    });

    expect(screen.getByTestId("status").textContent).toBe("not-guest");
    expect(sessionStorage.getItem("guest_mode")).toBeNull();
  });
});
