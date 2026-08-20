'use client'
import { useEffect, useState } from 'react'

/** Returns `value`, delayed by `delayMs` — updates only after `value` has stopped
 * changing for that long. Used to throttle autocomplete requests while typing
 * (FR-005/SC-004) without touching the caller's own state updates. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}
