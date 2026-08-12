/**
 * Pure functions for the Lighthouse performance check (022-lighthouse-performance-check).
 * No I/O, no child_process, no network — kept separate from lighthouse-check.mjs so
 * they're directly importable from Vitest (see frontend/tests/unit/lighthouse-report.test.ts).
 */

import { basename } from 'path'

/**
 * Maps a parsed Lighthouse JSON result ("LHR") to the RouteMetrics shape
 * (see specs/022-lighthouse-performance-check/data-model.md).
 */
export function extractRouteMetrics(lhr) {
  const rawScore = lhr?.categories?.performance?.score
  return {
    performanceScore: typeof rawScore === 'number' ? Math.round(rawScore * 100) : null,
    lcpMs: lhr?.audits?.['largest-contentful-paint']?.numericValue ?? null,
    tbtMs: lhr?.audits?.['total-blocking-time']?.numericValue ?? null,
    cls: lhr?.audits?.['cumulative-layout-shift']?.numericValue ?? null,
  }
}

function formatScore(value) {
  return value === null || value === undefined ? '—' : String(Math.round(value))
}

function formatMs(value) {
  return value === null || value === undefined ? '—' : String(Math.round(value))
}

function formatCls(value) {
  return value === null || value === undefined ? '—' : value.toFixed(3)
}

function summaryRow(route) {
  if (route.status === 'failed') {
    return `| \`${route.path}\` | — | — | — | — | ❌ 失敗（${route.failureReason}） |`
  }
  const m = route.metrics
  return `| \`${route.path}\` | ${formatScore(m.performanceScore)} | ${formatMs(m.lcpMs)} | ${formatMs(m.tbtMs)} | ${formatCls(m.cls)} | ✅ 成功 |`
}

function detailSection(route) {
  if (route.status === 'failed') {
    return [`### \`${route.path}\``, '', '- 狀態：❌ 失敗', `- 原因：${route.failureReason}`].join('\n')
  }
  const m = route.metrics
  return [
    `### \`${route.path}\``,
    '',
    `- Performance 分數：${formatScore(m.performanceScore)} / 100`,
    `- LCP（最大內容繪製）：${formatMs(m.lcpMs)} ms`,
    `- TBT（總阻塞時間）：${formatMs(m.tbtMs)} ms`,
    `- CLS（累計版面配置位移）：${formatCls(m.cls)}`,
    `- 原始 Lighthouse 報告：\`${basename(route.rawReportPath)}\`（同目錄）`,
  ].join('\n')
}

/**
 * Renders the consolidated Traditional-Chinese Markdown report
 * (see specs/022-lighthouse-performance-check/contracts/report-format.md).
 *
 * @param {{ baseUrl: string, guestId: string, finishedAt: string }} run
 * @param {Array<{ path: string, status: 'success'|'failed', failureReason: string|null, metrics: object|null, rawReportPath: string }>} routeTargets
 */
export function renderConsolidatedReport(run, routeTargets) {
  const successCount = routeTargets.filter((r) => r.status === 'success').length
  const failCount = routeTargets.length - successCount

  const header = [
    '# Lighthouse 效能檢測報告',
    '',
    `- **產出時間**：${run.finishedAt}`,
    `- **測試網址**：${run.baseUrl}`,
    `- **訪客身分**：guest_id=${run.guestId}（透過 POST /auth/guest 取得）`,
    `- **測試路徑數**：${routeTargets.length}（成功 ${successCount}，失敗 ${failCount}）`,
  ].join('\n')

  const summaryTable = [
    '## 總覽',
    '',
    '| 路徑 | Performance 分數 | LCP (ms) | TBT (ms) | CLS | 狀態 |',
    '|---|---|---|---|---|---|',
    ...routeTargets.map(summaryRow),
  ].join('\n')

  const details = ['## 各路徑詳細結果', '', routeTargets.map(detailSection).join('\n\n')].join('\n')

  return [header, '', summaryTable, '', details, ''].join('\n')
}
