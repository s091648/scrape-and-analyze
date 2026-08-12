#!/usr/bin/env node
/**
 * Lighthouse performance check across configured routes (022-lighthouse-performance-check).
 *
 * Usage: node scripts/lighthouse-check.mjs --url <baseUrl> --routes </,/articles,...>
 * (runs inside the frontend Docker container via `make lighthouse-check` — see Makefile)
 *
 * Obtains a guest identity via POST /api/proxy/auth/guest as a pre-flight health check and
 * for traceability in the report, but does NOT rely on it to make pages render correctly:
 * none of the target routes are gated by frontend/middleware.ts, and the app bootstraps its
 * own guest session on load exactly like a real anonymous visitor's browser would (see
 * specs/022-lighthouse-performance-check/research.md §3). Each route still gets the token
 * via --extra-headers for forward-compatibility, in case a future change starts honoring it.
 */

import { execFile } from 'child_process'
import { promisify } from 'util'
import { existsSync } from 'fs'
import { mkdir, readdir, readFile, writeFile } from 'fs/promises'
import { join } from 'path'
import { extractRouteMetrics, renderConsolidatedReport } from './lib/lighthouse-report.mjs'

const execFileAsync = promisify(execFile)

const DEFAULT_URL = 'http://frontend_prod:3000'
const DEFAULT_ROUTES = '/,/articles,/graph,/tags'
const LIGHTHOUSE_TIMEOUT_MS = 60_000
const OUTPUT_ROOT = process.env.LIGHTHOUSE_OUTPUT_ROOT || join(process.cwd(), 'lighthouse-reports')
// Reused rather than reinstalled — this is the same Chromium the `frontend` image already
// downloads for Playwright E2E tests (Dockerfile.dev's startup `npx playwright install`).
const PLAYWRIGHT_CACHE_DIR = process.env.PLAYWRIGHT_BROWSERS_PATH || '/root/.cache/ms-playwright'
const PLAYWRIGHT_INSTALL_HINT =
  'docker compose run --rm frontend node_modules/.bin/playwright install chromium --with-deps'

function parseArgs(argv) {
  const args = { url: DEFAULT_URL, routes: DEFAULT_ROUTES, failOnError: false }
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--url') args.url = argv[++i]
    else if (argv[i] === '--routes') args.routes = argv[++i]
    else if (argv[i] === '--fail-on-error') args.failOnError = true
  }
  const routes = args.routes
    .split(',')
    .map((r) => r.trim())
    .filter(Boolean)
  return { baseUrl: args.url.replace(/\/$/, ''), routes, failOnError: args.failOnError }
}

function decodeGuestId(jwt) {
  try {
    const payload = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64url').toString('utf8'))
    return payload.guest_id ?? '未知'
  } catch {
    return '未知'
  }
}

async function fetchGuestToken(baseUrl) {
  const res = await fetch(`${baseUrl}/api/proxy/auth/guest`, { method: 'POST' })
  if (!res.ok) {
    throw new Error(`POST /api/proxy/auth/guest 回應失敗（HTTP ${res.status}）`)
  }
  const data = await res.json()
  return { accessToken: data.access_token, guestId: decodeGuestId(data.access_token) }
}

/**
 * Finds an already-downloaded Chromium binary under Playwright's cache directory.
 *
 * Deliberately scans the filesystem instead of calling `require('playwright').chromium
 * .executablePath()` — that API returns the path for whichever revision the currently
 * *installed* `playwright` package version expects, which can silently drift out of sync
 * with what's actually been downloaded to the (long-lived, named-volume) cache directory
 * whenever `playwright` gets bumped without a corresponding `playwright install`. Any
 * modern Chromium build already present is perfectly fine for a Lighthouse audit — this
 * doesn't need to match Playwright's own pinned revision exactly.
 */
async function resolveChromePath() {
  let entries
  try {
    entries = await readdir(PLAYWRIGHT_CACHE_DIR)
  } catch {
    throw new Error(`找不到 Playwright 瀏覽器快取目錄（${PLAYWRIGHT_CACHE_DIR}）。請先執行：${PLAYWRIGHT_INSTALL_HINT}`)
  }

  const chromiumDirs = entries.filter((name) => /^chromium-\d+$/.test(name)).sort().reverse()
  for (const dir of chromiumDirs) {
    for (const relPath of ['chrome-linux64/chrome', 'chrome-linux/chrome']) {
      const candidate = join(PLAYWRIGHT_CACHE_DIR, dir, relPath)
      if (existsSync(candidate)) return candidate
    }
  }

  throw new Error(`在 ${PLAYWRIGHT_CACHE_DIR} 找不到可用的 Chromium 執行檔。請先執行：${PLAYWRIGHT_INSTALL_HINT}`)
}

function routeFileName(path, index) {
  const slug = path === '/' ? 'root' : path.replace(/^\//, '').replace(/\//g, '_')
  return `route-${index}-${slug}.json`
}

async function runLighthouseForRoute({ baseUrl, path, accessToken, chromePath, outputDir, index }) {
  const url = `${baseUrl}${path}`
  const outputPath = join(outputDir, routeFileName(path, index))
  const extraHeaders = JSON.stringify({ Authorization: `Bearer ${accessToken}` })

  try {
    await execFileAsync(
      'npx',
      [
        '--yes',
        'lighthouse',
        url,
        '--output=json',
        `--output-path=${outputPath}`,
        '--chrome-flags=--headless=new --no-sandbox --disable-gpu',
        `--extra-headers=${extraHeaders}`,
        '--only-categories=performance',
        '--quiet',
      ],
      {
        env: { ...process.env, CHROME_PATH: chromePath },
        timeout: LIGHTHOUSE_TIMEOUT_MS,
        maxBuffer: 10 * 1024 * 1024,
      }
    )
  } catch (err) {
    const reason = err.killed ? '逾時' : `Lighthouse 執行失敗（${String(err.message).split('\n')[0]}）`
    return { path, status: 'failed', failureReason: reason, metrics: null, rawReportPath: outputPath }
  }

  let lhr
  try {
    lhr = JSON.parse(await readFile(outputPath, 'utf8'))
  } catch (err) {
    return {
      path,
      status: 'failed',
      failureReason: `無法解析 Lighthouse 輸出（${err.message}）`,
      metrics: null,
      rawReportPath: outputPath,
    }
  }

  return { path, status: 'success', failureReason: null, metrics: extractRouteMetrics(lhr), rawReportPath: outputPath }
}

function makeRunId(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${date.getUTCFullYear()}${pad(date.getUTCMonth() + 1)}${pad(date.getUTCDate())}` +
    `-${pad(date.getUTCHours())}${pad(date.getUTCMinutes())}${pad(date.getUTCSeconds())}`
  )
}

async function main() {
  const { baseUrl, routes, failOnError } = parseArgs(process.argv.slice(2))

  let accessToken, guestId
  try {
    ;({ accessToken, guestId } = await fetchGuestToken(baseUrl))
  } catch (err) {
    console.error(`❌ 無法取得訪客身分，中止檢查：${err.message}`)
    process.exitCode = 1
    return
  }

  let chromePath
  try {
    chromePath = await resolveChromePath()
  } catch (err) {
    console.error(`❌ ${err.message}`)
    process.exitCode = 1
    return
  }

  const runId = makeRunId()
  const outputDir = join(OUTPUT_ROOT, runId)
  await mkdir(outputDir, { recursive: true })

  const routeTargets = []
  for (let i = 0; i < routes.length; i++) {
    const path = routes[i]
    const result = await runLighthouseForRoute({ baseUrl, path, accessToken, chromePath, outputDir, index: i })
    routeTargets.push(result)
    console.log(result.status === 'success' ? `✅ ${path}` : `❌ ${path}（${result.failureReason}）`)
  }

  const report = renderConsolidatedReport({ baseUrl, guestId, finishedAt: new Date().toISOString() }, routeTargets)
  const reportPath = join(outputDir, 'report.md')
  await writeFile(reportPath, report, 'utf8')

  console.log(`報告已產出：${reportPath}`)

  // --fail-on-error: opt-in, used by CI to gate PR merges on the check actually
  // running cleanly (Chrome/network/timeout issues), without yet gating on the
  // Performance/LCP/TBT/CLS numbers themselves (022-lighthouse-performance-check, US3).
  // Left off by default so local runs stay exploratory per T009's original contract.
  if (failOnError && routeTargets.some((r) => r.status === 'failed')) {
    process.exitCode = 1
  }
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})
