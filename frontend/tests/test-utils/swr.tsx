import { SWRConfig } from 'swr'

/** RTL `render(ui, { wrapper: SWRTestWrapper })` — gives that render() call (and every
 * `rerender()` from the same result, which RTL automatically re-wraps with the same `wrapper`)
 * its own empty SWR cache.
 *
 * SWR's default cache (used whenever there's no ancestor <SWRConfig provider>, exactly the app's
 * own real setup at runtime — lib/swr/provider.tsx) is otherwise a module-level singleton shared
 * by every `useSWR` call for the lifetime of the test file's module graph — so two `it()` blocks
 * in the same file that happen to fetch the same key (same params/locale/token) would otherwise
 * silently share cached data / dedupe a real fetch (SWR's default `dedupingInterval` is 2000ms,
 * comfortably longer than most tests take to run back-to-back), breaking `toHaveBeenCalledTimes`
 * assertions in a way that has nothing to do with the behavior under test. */
export function SWRTestWrapper({ children }: { children: React.ReactNode }) {
  return <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{children}</SWRConfig>
}

/** For a test that needs *multiple* render()/renderHook() calls to deliberately share one cache
 * within that single test (e.g. asserting two mounted components dedupe into one fetch) while
 * still staying isolated from every *other* test — `SWRTestWrapper` can't do this alone, since
 * each render() call mounts its own fresh `<SWRTestWrapper>` instance (and so its own fresh
 * Map). Call this once per test, reuse the returned component across that test's render calls:
 *
 *   const Wrapper = createSWRTestWrapper()
 *   renderHook(() => useThing(), { wrapper: Wrapper })
 *   renderHook(() => useThing(), { wrapper: Wrapper }) // shares the first call's cache
 */
export function createSWRTestWrapper() {
  const cache = new Map()
  return function ScopedSWRTestWrapper({ children }: { children: React.ReactNode }) {
    return <SWRConfig value={{ provider: () => cache, dedupingInterval: 0 }}>{children}</SWRConfig>
  }
}
