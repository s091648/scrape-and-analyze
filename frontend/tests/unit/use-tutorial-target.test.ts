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
