"use client";
import { useEffect, useState } from "react";

const FIND_TIMEOUT_MS = 3000;

/**
 * Locates the DOM element identified by `targetId` and tracks its bounding
 * rect. Polls briefly for the element to mount (covers post-navigation async
 * content), then keeps the rect in sync via resize/scroll/ResizeObserver.
 * Returns null when `targetId` is undefined, the element is never found
 * within the timeout, or no target is being tracked.
 */
export function useTutorialTarget(targetId: string | undefined): DOMRect | null {
  const [rect, setRect] = useState<DOMRect | null>(null);

  // Reset immediately (during render, not in an effect) whenever targetId
  // changes, so stale rects from a previous target never leak through.
  const [prevTargetId, setPrevTargetId] = useState(targetId);
  if (targetId !== prevTargetId) {
    setPrevTargetId(targetId);
    if (rect !== null) setRect(null);
  }

  useEffect(() => {
    if (!targetId) return;

    const id = targetId;
    let rafId: number | undefined;
    let cleanupTracking: (() => void) | undefined;
    let cancelled = false;
    const start = Date.now();

    function trackElement(el: Element) {
      const update = () => setRect(el.getBoundingClientRect());
      update();
      window.addEventListener("resize", update);
      window.addEventListener("scroll", update, true);
      const observer = new ResizeObserver(update);
      observer.observe(el);
      return () => {
        window.removeEventListener("resize", update);
        window.removeEventListener("scroll", update, true);
        observer.disconnect();
      };
    }

    function tryFind() {
      if (cancelled) return;
      const el = document.getElementById(id);
      if (el) {
        cleanupTracking = trackElement(el);
        return;
      }
      if (Date.now() - start < FIND_TIMEOUT_MS) {
        rafId = requestAnimationFrame(tryFind);
      } else {
        setRect(null);
      }
    }

    tryFind();

    return () => {
      cancelled = true;
      if (rafId !== undefined) cancelAnimationFrame(rafId);
      cleanupTracking?.();
    };
  }, [targetId]);

  return rect;
}
