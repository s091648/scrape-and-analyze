"use client";
import { useEffect, useState } from "react";

const FIND_TIMEOUT_MS = 3000;
// Number of consecutive unchanged frames required before considering the
// rect "settled" and stopping the per-frame poll.
const STABLE_FRAMES_NEEDED = 10;
// Hard cap on how long the settle poll may run, in case the layout never
// truly stops shifting (e.g. a slow-loading image keeps nudging things).
const MAX_SETTLE_MS = 3000;

function sameRect(a: DOMRect, b: DOMRect): boolean {
  return a.top === b.top && a.left === b.left && a.width === b.width && a.height === b.height;
}

/**
 * Locates the DOM element identified by `targetId` and tracks its bounding
 * rect. Polls briefly for the element to mount (covers post-navigation async
 * content), then keeps the rect in sync via resize/scroll/ResizeObserver —
 * plus a per-frame poll right after the target is found that keeps
 * re-measuring until the rect stops changing for several consecutive
 * frames (bounded by MAX_SETTLE_MS). A fixed-duration settle window isn't
 * enough here: a layout shift caused by e.g. a scrollbar appearing/
 * disappearing across a route change, or a target that only exists once an
 * async-loaded list finishes rendering, can each take a variable amount of
 * time to stop moving — neither fires `resize`, changes the target's own
 * size (so a ResizeObserver on it doesn't fire), nor is reliably caught by
 * observing `document.documentElement`. Polling until convergence (instead
 * of for a fixed duration) has been observed to catch both cases reliably.
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
    let start = Date.now();

    function trackElement(el: Element) {
      const update = () => setRect(el.getBoundingClientRect());
      update();

      let lastSettleRect: DOMRect | null = null;
      let stableFrames = 0;
      const settleDeadline = Date.now() + MAX_SETTLE_MS;
      function settlePoll() {
        const next = el.getBoundingClientRect();
        if (lastSettleRect && sameRect(lastSettleRect, next)) {
          stableFrames++;
        } else {
          stableFrames = 0;
          lastSettleRect = next;
          setRect(next);
        }
        if (stableFrames < STABLE_FRAMES_NEEDED && Date.now() < settleDeadline) {
          rafId = requestAnimationFrame(settlePoll);
        }
      }
      rafId = requestAnimationFrame(settlePoll);

      window.addEventListener("resize", update);
      window.addEventListener("scroll", update, true);
      const resizeObserver = new ResizeObserver(update);
      resizeObserver.observe(el);

      // Safety net: if the tracked element is ever removed from the DOM
      // (e.g. the list it belongs to re-renders and swaps in a new node for
      // the same id), stop tracking the stale reference and restart the
      // search so the (possibly new) element gets picked up again.
      const mutationObserver = new MutationObserver(() => {
        if (!el.isConnected) {
          cleanupTracking?.();
          cleanupTracking = undefined;
          start = Date.now();
          tryFind();
        }
      });
      mutationObserver.observe(document.body, { childList: true, subtree: true });

      return () => {
        if (rafId !== undefined) cancelAnimationFrame(rafId);
        window.removeEventListener("resize", update);
        window.removeEventListener("scroll", update, true);
        resizeObserver.disconnect();
        mutationObserver.disconnect();
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
