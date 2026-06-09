#!/usr/bin/env node
/**
 * Scans frontend source for React Context providers, consumers,
 * and cross-context dependencies. Outputs frontend-context.json.
 *
 * Usage: node scripts/generate-frontend-context.mjs
 * (runs inside the frontend Docker container where CWD=/app)
 *
 * Reads:  app/, components/, lib/  (relative to CWD)
 * Writes: site/guide/architecture/frontend-context.json
 */

import { readdir, readFile, writeFile, mkdir } from 'fs/promises'
import { join, dirname, relative, sep } from 'path'

// ─── Config ───────────────────────────────────────────────────────────────────

const CWD = process.cwd()
const SCAN_DIRS = ['app', 'components', 'lib']
const OUTPUT_PATH = process.env.OUTPUT_PATH || join(CWD, 'site/public/guide/architecture/frontend-context.json')

// Known provider files and their metadata (for reliable detection)
const PROVIDER_DEFS = [
  {
    id: 'session',
    name: 'SessionProviderWrapper',
    file: 'lib/providers/session-provider.tsx',
    hookName: 'useSession',
    importPath: 'next-auth/react',
    description: 'Wraps next-auth SessionProvider, refetchOnWindowFocus=false',
  },
  {
    id: 'topic',
    name: 'TopicProvider',
    file: 'lib/providers/topic-provider.tsx',
    hookName: 'useTopic',
    importPath: '@/lib/providers',
    description: 'Topics list, selectedTopicId, URL sync, localStorage',
  },
  {
    id: 'i18n',
    name: 'I18nProvider',
    file: 'lib/providers/i18n-provider.tsx',
    hookName: 'useI18n',
    importPath: '@/lib/providers',
    description: 'Locale, translations, t(), localStorage',
  },
  {
    id: 'guestMode',
    name: 'GuestModeProvider',
    file: 'lib/providers/guest-mode-provider.tsx',
    hookName: 'useGuestMode',
    importPath: '@/lib/providers',
    description: 'isGuestMode, sessionStorage',
  },
]

// Hook names to scan for (including next-auth's useSession)
const HOOK_PATTERNS = PROVIDER_DEFS.map(p => ({
  contextId: p.id,
  hookName: p.hookName,
  importPath: p.importPath,
}))

// ─── File walking ──────────────────────────────────────────────────────────────

async function walkDir(dir, exts = ['.tsx', '.ts']) {
  const results = []
  let entries
  try { entries = await readdir(dir, { withFileTypes: true }) } catch { return results }
  for (const entry of entries) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '.next' || entry.name === '__tests__') continue
      results.push(...await walkDir(full, exts))
    } else if (exts.some(ext => entry.name.endsWith(ext))) {
      results.push(full)
    }
  }
  return results
}

// ─── Nesting hierarchy detection ──────────────────────────────────────────────

function detectNesting(barrelContent) {
  // Parse AppProviders JSX to determine nesting order.
  // Strategy: find JSX elements in order of opening tags — outermost first.
  const jsxOpenRe = /<(\w+Provider\w*|SessionProviderWrapper)/g
  const order = []
  let m
  while ((m = jsxOpenRe.exec(barrelContent)) !== null) {
    const name = m[1]
    if (!order.includes(name)) order.push(name)
  }

  // Map provider component names to IDs
  const nameToId = Object.fromEntries(PROVIDER_DEFS.map(p => [p.name, p.id]))
  const idOrder = order.map(n => nameToId[n]).filter(Boolean)

  // Build parent-child
  const parentMap = {}
  for (let i = 0; i < idOrder.length; i++) {
    const id = idOrder[i]
    const parent = i > 0 ? idOrder[i - 1] : null
    parentMap[id] = parent
  }

  return { idOrder, parentMap }
}

// ─── Consumer scanning ────────────────────────────────────────────────────────

function findConsumers(file, content) {
  const rel = relative(CWD, file).replace(/\\/g, '/')
  const results = []

  for (const pat of HOOK_PATTERNS) {
    // Match: const { ... } = useXxx(...)  OR  useXxx(...)
    const hookRe = new RegExp(
      `(?:const\\s*(\\{[^}]*\\})?\\s*=\\s*)?${pat.hookName}\\s*\\(`,
      'g'
    )
    let m
    while ((m = hookRe.exec(content)) !== null) {
      const line = content.substring(0, m.index).split('\n').length
      const destructured = m[1]?.trim() || ''
      results.push({
        contextId: pat.contextId,
        site: {
          file: rel,
          line,
          destructured,
        },
      })
    }
  }

  return results
}

// ─── Cross-context dependency detection ───────────────────────────────────────

function findCrossContextDeps(providerFile, providerId, content) {
  const rel = relative(CWD, providerFile).replace(/\\/g, '/')
  const deps = []

  for (const pat of HOOK_PATTERNS) {
    if (pat.contextId === providerId) continue
    const hookRe = new RegExp(
      `const\\s*(\\{[^}]*\\})\\s*=\\s*${pat.hookName}\\s*\\(`,
      'g'
    )
    let m
    while ((m = hookRe.exec(content)) !== null) {
      const line = content.substring(0, m.index).split('\n').length
      deps.push({
        from: providerId,
        to: pat.contextId,
        description: `${PROVIDER_DEFS.find(p => p.id === providerId)?.name} internally uses ${pat.hookName}()`,
        evidence: {
          file: rel,
          line,
          code: `const ${m[1].trim()} = ${pat.hookName}()`,
        },
      })
    }
  }
  return deps
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  // 1. Collect all source files
  const files = []
  for (const dir of SCAN_DIRS) {
    files.push(...await walkDir(join(CWD, dir)))
  }

  // 2. Parse barrel file for nesting hierarchy
  const barrelPath = join(CWD, 'lib/providers/index.tsx')
  const barrelContent = await readFile(barrelPath, 'utf-8')
  const { idOrder, parentMap } = detectNesting(barrelContent)

  // 3. Scan for consumers and cross-context deps
  const allConsumerSites = []  // { contextId, site: { file, line, destructured } }
  const crossContextDeps = []

  const providerFiles = new Set(PROVIDER_DEFS.map(p => join(CWD, p.file)))

  for (const file of files) {
    const content = await readFile(file, 'utf-8')
    const rel = relative(CWD, file).replace(/\\/g, '/')

    // Skip provider files for consumer scanning (they define the hooks)
    if (providerFiles.has(file)) {
      // But scan them for cross-context dependencies
      const providerDef = PROVIDER_DEFS.find(p => p.file === rel)
      if (providerDef) {
        crossContextDeps.push(...findCrossContextDeps(file, providerDef.id, content))
      }
      continue
    }

    allConsumerSites.push(...findConsumers(file, content))
  }

  // 4. Group consumers by contextId
  const consumersByContext = {}
  for (const { contextId, site } of allConsumerSites) {
    if (!consumersByContext[contextId]) consumersByContext[contextId] = []
    consumersByContext[contextId].push(site)
  }

  // 5. Build output
  const providers = PROVIDER_DEFS.map(p => ({
    id: p.id,
    name: p.name,
    file: p.file,
    hookName: p.hookName,
    importPath: p.importPath,
    parent: parentMap[p.id] ?? null,
    nestingLevel: idOrder.indexOf(p.id),
    children: idOrder.filter(cid => parentMap[cid] === p.id),
    consumerCount: consumersByContext[p.id]?.length ?? 0,
    description: p.description,
  }))

  const consumers = PROVIDER_DEFS.map(p => ({
    contextId: p.id,
    hookName: p.hookName,
    sites: consumersByContext[p.id] ?? [],
  }))

  const totalSites = Object.values(consumersByContext).reduce((s, arr) => s + arr.length, 0)
  const mostConsumed = providers.reduce((a, b) => a.consumerCount > b.consumerCount ? a : b)

  const output = {
    generated_at: new Date().toISOString(),
    providers,
    consumers,
    crossContextDeps,
    summary: {
      totalProviders: providers.length,
      totalConsumerSites: totalSites,
      maxNestingDepth: idOrder.length - 1,
      mostConsumedContext: mostConsumed.id,
    },
  }

  // 6. Write output
  await mkdir(dirname(OUTPUT_PATH), { recursive: true })
  await writeFile(OUTPUT_PATH, JSON.stringify(output, null, 2) + '\n')
  console.log(`Wrote ${OUTPUT_PATH}`)
  console.log(`  ${providers.length} providers, ${totalSites} consumer sites, ${crossContextDeps.length} cross-context deps`)
}

main().catch(err => { console.error(err); process.exit(1) })
