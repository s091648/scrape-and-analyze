import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTypewriter } from '@/components/features/chat/use-typewriter'

describe('useTypewriter', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the target immediately on first mount (no animation for the initial value)', () => {
    const { result } = renderHook(() => useTypewriter('Hello'))
    expect(result.current).toBe('Hello')
  })

  it('reveals an extended target gradually rather than jumping straight to it', () => {
    vi.useFakeTimers()
    let target = 'Hello'
    const { result, rerender } = renderHook(() => useTypewriter(target))
    expect(result.current).toBe('Hello')

    target = 'Hello, this is a much longer sentence that keeps going for a while.'
    rerender()

    // Immediately after the target grows, the display hasn't caught up yet.
    expect(result.current).toBe('Hello')

    act(() => {
      vi.advanceTimersByTime(20)
    })
    expect(result.current.length).toBeGreaterThan('Hello'.length)
    expect(result.current.length).toBeLessThan(target.length)
  })

  it('eventually catches up to the full target', () => {
    vi.useFakeTimers()
    let target = ''
    const { result, rerender } = renderHook(() => useTypewriter(target))

    target = 'A reasonably long piece of text that should fully reveal given enough time.'
    rerender()

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(result.current).toBe(target)
  })

  it('snaps immediately when the new target is not a simple extension of what is shown', () => {
    vi.useFakeTimers()
    let target = ''
    const { result, rerender } = renderHook(() => useTypewriter(target))

    // Start it mid-reveal on the first turn's answer, so there's something already displayed
    // that the second turn's text can genuinely mismatch against.
    target = 'First turn answer, fairly long so it would normally still be animating.'
    rerender()
    act(() => {
      vi.advanceTimersByTime(20)
    })
    expect(result.current.length).toBeGreaterThan(0)
    expect(result.current.length).toBeLessThan(target.length)

    // Switching to a completely different turn's text must not try to "type" through the
    // mismatch — it should show the new text right away.
    target = 'Second turn answer.'
    rerender()

    expect(result.current).toBe('Second turn answer.')
  })

  it('does not re-animate when the target stays the same across re-renders', () => {
    vi.useFakeTimers()
    const target = 'Settled text for an already-finished turn.'
    const { result, rerender } = renderHook(() => useTypewriter(target))
    expect(result.current).toBe(target)

    rerender()
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(result.current).toBe(target)
  })

  it('stops advancing once it reaches the target (no runaway interval)', () => {
    vi.useFakeTimers()
    let target = 'Short'
    const { result, rerender } = renderHook(() => useTypewriter(target))
    target = 'Short update'
    rerender()

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(result.current).toBe('Short update')

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(result.current).toBe('Short update')
  })
})
