import { describe, it, expect } from 'vitest'
import { extractRouteMetrics, renderConsolidatedReport } from '../../scripts/lib/lighthouse-report.mjs'

function makeLhrFixture({ score = 0.82, lcp = 1820, tbt = 120, cls = 0.03 } = {}) {
  return {
    categories: { performance: { score } },
    audits: {
      'largest-contentful-paint': { numericValue: lcp },
      'total-blocking-time': { numericValue: tbt },
      'cumulative-layout-shift': { numericValue: cls },
    },
  }
}

describe('extractRouteMetrics', () => {
  it('maps a realistic LHR JSON result to RouteMetrics', () => {
    const lhr = makeLhrFixture({ score: 0.82, lcp: 1820.4, tbt: 120, cls: 0.03 })

    expect(extractRouteMetrics(lhr)).toEqual({
      performanceScore: 82,
      lcpMs: 1820.4,
      tbtMs: 120,
      cls: 0.03,
    })
  })

  it('rounds the 0-1 performance score to an integer 0-100', () => {
    const lhr = makeLhrFixture({ score: 0.755 })
    expect(extractRouteMetrics(lhr).performanceScore).toBe(76)
  })

  it('returns null fields when audits are missing rather than throwing', () => {
    expect(extractRouteMetrics({})).toEqual({
      performanceScore: null,
      lcpMs: null,
      tbtMs: null,
      cls: null,
    })
  })
})

describe('renderConsolidatedReport', () => {
  const run = { baseUrl: 'http://frontend_prod:3000', guestId: 'guest-123', finishedAt: '2026-08-09T14:30:00.000Z' }

  it('renders a summary table row and detail section for every successful route', () => {
    const routeTargets = [
      {
        path: '/',
        status: 'success',
        failureReason: null,
        metrics: { performanceScore: 82, lcpMs: 1820, tbtMs: 120, cls: 0.03 },
        rawReportPath: '/tmp/route-0-root.json',
      },
      {
        path: '/articles',
        status: 'success',
        failureReason: null,
        metrics: { performanceScore: 75, lcpMs: 2400, tbtMs: 340, cls: 0.05 },
        rawReportPath: '/tmp/route-1-articles.json',
      },
    ]

    const report = renderConsolidatedReport(run, routeTargets)

    expect(report).toContain('| `/` | 82 | 1820 | 120 | 0.030 | ✅ 成功 |')
    expect(report).toContain('| `/articles` | 75 | 2400 | 340 | 0.050 | ✅ 成功 |')
    expect(report).toContain('### `/`')
    expect(report).toContain('LCP（最大內容繪製）：1820 ms')
    expect(report).toContain('route-0-root.json')
  })

  it('shows a failed route as em-dashes plus a Traditional-Chinese reason, never omitted', () => {
    const routeTargets = [
      {
        path: '/graph',
        status: 'failed',
        failureReason: '逾時',
        metrics: null,
        rawReportPath: '/tmp/route-2-graph.json',
      },
    ]

    const report = renderConsolidatedReport(run, routeTargets)

    expect(report).toContain('| `/graph` | — | — | — | — | ❌ 失敗（逾時） |')
    expect(report).toContain('### `/graph`')
    expect(report).toContain('狀態：❌ 失敗')
    expect(report).toContain('原因：逾時')
  })

  it('reports the success/failure counts and guest identity in the header', () => {
    const routeTargets = [
      { path: '/', status: 'success', failureReason: null, metrics: { performanceScore: 90, lcpMs: 1000, tbtMs: 10, cls: 0 }, rawReportPath: 'a.json' },
      { path: '/tags', status: 'failed', failureReason: 'HTTP 500', metrics: null, rawReportPath: 'b.json' },
    ]

    const report = renderConsolidatedReport(run, routeTargets)

    expect(report).toContain('guest_id=guest-123')
    expect(report).toContain('測試路徑數**：2（成功 1，失敗 1）')
  })

  it('writes every heading and label in Traditional Chinese', () => {
    const routeTargets = [
      { path: '/', status: 'success', failureReason: null, metrics: { performanceScore: 90, lcpMs: 1000, tbtMs: 10, cls: 0 }, rawReportPath: 'a.json' },
    ]

    const report = renderConsolidatedReport(run, routeTargets)

    for (const heading of ['# Lighthouse 效能檢測報告', '## 總覽', '## 各路徑詳細結果']) {
      expect(report).toContain(heading)
    }
    // No stray English section labels leaking in place of the Traditional-Chinese ones.
    expect(report).not.toMatch(/## (Overview|Summary|Details)/)
  })
})
