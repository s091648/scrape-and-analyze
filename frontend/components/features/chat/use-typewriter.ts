'use client'
import { useEffect, useRef, useState } from 'react'

const TICK_MS = 20
const MIN_STEP_CHARS = 2
const CATCH_UP_FRACTION = 0.15

/** Reveals `target` incrementally instead of snapping the displayed text to it on every update.
 * The backend legitimately delivers a full sentence or paragraph in a single SSE chunk (Gemini's
 * thinking-summary deltas especially — see AnswerDisplay's ThinkingBlock), which without this
 * makes the answer visibly jump in big blocks rather than feel like it's streaming in.
 *
 * The per-tick step is proportional to how far behind `target` the display currently is, so a
 * big chunk that just landed doesn't take unnaturally long to finish revealing, while small
 * steady increments still read at a typewriter-like pace instead of instantly snapping.
 *
 * Any change to `target` that ISN'T a simple extension of what's already shown — switching to a
 * different turn, or any other non-append change — snaps to the new value immediately instead of
 * animating; there's nothing sensible to "type" toward from unrelated text. */
export function useTypewriter(target: string): string {
  const [displayed, setDisplayed] = useState(target)
  const displayedRef = useRef(displayed)

  useEffect(() => {
    if (target === displayedRef.current) return

    if (!target.startsWith(displayedRef.current)) {
      displayedRef.current = target
      setDisplayed(target)
      return
    }

    const id = setInterval(() => {
      setDisplayed(prev => {
        if (prev.length >= target.length) {
          clearInterval(id)
          return prev
        }
        const remaining = target.length - prev.length
        const step = Math.max(MIN_STEP_CHARS, Math.ceil(remaining * CATCH_UP_FRACTION))
        const next = target.slice(0, prev.length + step)
        displayedRef.current = next
        return next
      })
    }, TICK_MS)
    return () => clearInterval(id)
  }, [target])

  return displayed
}
