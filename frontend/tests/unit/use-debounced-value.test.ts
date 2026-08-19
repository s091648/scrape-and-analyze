import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebouncedValue } from '@/hooks/use-debounced-value'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useDebouncedValue', () => {
  it('returns the initial value immediately', () => {
    const { result } = renderHook(() => useDebouncedValue('initial', 300))
    expect(result.current).toBe('initial')
  })

  it('does not update before the delay elapses', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: 'a' },
    })
    rerender({ value: 'ab' })
    act(() => { vi.advanceTimersByTime(299) })
    expect(result.current).toBe('a')
  })

  it('updates once the delay elapses', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: 'a' },
    })
    rerender({ value: 'ab' })
    act(() => { vi.advanceTimersByTime(300) })
    expect(result.current).toBe('ab')
  })

  it('resets the timer on rapid successive changes — only the final value is ever committed', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: 'a' },
    })
    rerender({ value: 'ab' })
    act(() => { vi.advanceTimersByTime(200) })
    rerender({ value: 'abc' })
    act(() => { vi.advanceTimersByTime(200) })
    expect(result.current).toBe('a') // neither intermediate value has committed yet

    act(() => { vi.advanceTimersByTime(100) })
    expect(result.current).toBe('abc')
  })

  it('clears the pending timeout on unmount (no update after unmount)', () => {
    const clearSpy = vi.spyOn(window, 'clearTimeout')
    const { rerender, unmount } = renderHook(({ value }) => useDebouncedValue(value, 300), {
      initialProps: { value: 'a' },
    })
    rerender({ value: 'ab' })
    unmount()
    expect(clearSpy).toHaveBeenCalled()
    clearSpy.mockRestore()
  })
})
