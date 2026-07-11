import { describe, it, expect, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useIsMobile } from "@/components/features/tutorial/use-is-mobile";

function setViewportWidth(width: number) {
  Object.defineProperty(window, "innerWidth", {
    writable: true,
    configurable: true,
    value: width,
  });
}

describe("useIsMobile", () => {
  afterEach(() => {
    setViewportWidth(1024);
  });

  it("returns false when viewport width is at or above the breakpoint", () => {
    setViewportWidth(1024);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });

  it("returns true when viewport width is below the breakpoint", () => {
    setViewportWidth(500);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it("updates when the window is resized across the breakpoint", () => {
    setViewportWidth(1024);
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);

    act(() => {
      setViewportWidth(500);
      window.dispatchEvent(new Event("resize"));
    });
    expect(result.current).toBe(true);

    act(() => {
      setViewportWidth(1024);
      window.dispatchEvent(new Event("resize"));
    });
    expect(result.current).toBe(false);
  });

  it("removes the resize listener on unmount", () => {
    setViewportWidth(1024);
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useIsMobile());
    unmount();
    expect(removeSpy).toHaveBeenCalledWith("resize", expect.any(Function));
    removeSpy.mockRestore();
  });
});
