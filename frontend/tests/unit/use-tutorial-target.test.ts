import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useTutorialTarget } from "@/components/features/tutorial/use-tutorial-target";

function mockRect(overrides: Partial<DOMRect> = {}): DOMRect {
  return {
    top: 10,
    left: 20,
    width: 100,
    height: 40,
    bottom: 50,
    right: 120,
    x: 20,
    y: 10,
    toJSON: () => ({}),
    ...overrides,
  } as DOMRect;
}

describe("useTutorialTarget", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    vi.restoreAllMocks();
  });

  it("returns null when targetId is undefined", () => {
    const { result } = renderHook(() => useTutorialTarget(undefined));
    expect(result.current).toBeNull();
  });

  it("returns the element's rect once it is found in the DOM", async () => {
    const el = document.createElement("div");
    el.id = "my-target";
    el.getBoundingClientRect = () => mockRect();
    document.body.appendChild(el);

    const { result } = renderHook(() => useTutorialTarget("my-target"));

    await waitFor(() => expect(result.current).not.toBeNull());
    expect(result.current?.width).toBe(100);
    expect(result.current?.top).toBe(10);
  });

  it("returns null when the target is never found within the timeout", async () => {
    vi.useFakeTimers();
    const rafSpy = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation((cb: FrameRequestCallback) => {
        return setTimeout(() => cb(0), 0) as unknown as number;
      });

    const { result } = renderHook(() => useTutorialTarget("never-appears"));

    await act(async () => {
      vi.advanceTimersByTime(3100);
      await Promise.resolve();
    });

    expect(result.current).toBeNull();
    rafSpy.mockRestore();
    vi.useRealTimers();
  });

  it("resets the search deadline when the tracked element is swapped out after the initial find window elapses", () => {
    vi.useFakeTimers();
    const rafSpy = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation((cb: FrameRequestCallback) => {
        return setTimeout(() => cb(0), 0) as unknown as number;
      });
    const cafSpy = vi
      .spyOn(window, "cancelAnimationFrame")
      .mockImplementation((id: number) => clearTimeout(id as unknown as ReturnType<typeof setTimeout>));

    class FakeMutationObserver {
      static instances: FakeMutationObserver[] = [];
      callback: MutationCallback;
      constructor(cb: MutationCallback) {
        this.callback = cb;
        FakeMutationObserver.instances.push(this);
      }
      observe() {}
      disconnect() {}
    }
    vi.stubGlobal("MutationObserver", FakeMutationObserver);

    const el = document.createElement("div");
    el.id = "swap-target";
    el.getBoundingClientRect = () => mockRect({ width: 100 });
    document.body.appendChild(el);

    const { result } = renderHook(() => useTutorialTarget("swap-target"));
    expect(result.current?.width).toBe(100);

    // Move well past the original 3s find-timeout window from mount.
    act(() => {
      vi.advanceTimersByTime(3500);
    });

    // Simulate the tracked node being removed from the DOM (e.g. a list
    // re-render swaps in a new node for the same id) — notify via the
    // MutationObserver callback, as the real observer would.
    document.body.removeChild(el);
    const observerInstance = FakeMutationObserver.instances[FakeMutationObserver.instances.length - 1];
    act(() => {
      observerInstance.callback([], observerInstance as unknown as MutationObserver);
    });

    // The replacement element doesn't exist yet — with the deadline reset,
    // the retry loop must keep polling instead of giving up immediately.
    expect(result.current?.width).toBe(100);

    const replacement = document.createElement("div");
    replacement.id = "swap-target";
    replacement.getBoundingClientRect = () => mockRect({ width: 250 });

    act(() => {
      vi.advanceTimersByTime(200);
      document.body.appendChild(replacement);
      vi.advanceTimersByTime(200);
    });

    expect(result.current?.width).toBe(250);

    rafSpy.mockRestore();
    cafSpy.mockRestore();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("recalculates the rect on window resize", async () => {
    const el = document.createElement("div");
    el.id = "resizing-target";
    let width = 100;
    el.getBoundingClientRect = () => mockRect({ width });
    document.body.appendChild(el);

    const { result } = renderHook(() => useTutorialTarget("resizing-target"));
    await waitFor(() => expect(result.current?.width).toBe(100));

    width = 250;
    act(() => {
      window.dispatchEvent(new Event("resize"));
    });

    await waitFor(() => expect(result.current?.width).toBe(250));
  });
});
