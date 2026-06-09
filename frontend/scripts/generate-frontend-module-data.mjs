#!/usr/bin/env node
/**
 * Scans frontend source for module metadata: exports, props, hooks,
 * 'use client' directives, and docstrings.
 * Outputs frontend-module-data.json.
 *
 * Usage: node scripts/generate-frontend-module-data.mjs
 * (runs inside the frontend Docker container where CWD=/app)
 *
 * Reads:  app/, components/, lib/  (relative to CWD)
 * Writes: site/guide/architecture/frontend-module-data.json
 */

import { readdir, readFile, writeFile, mkdir } from 'fs/promises'
import { join, relative } from 'path'

// ─── Config ───────────────────────────────────────────────────────────────────

const CWD = process.cwd()
const SCAN_DIRS = ['app', 'components', 'lib']
const OUTPUT_PATH = join(CWD, 'site/guide/architecture/frontend-module-data.json')

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

// ─── Scanning ─────────────────────────────────────────────────────────────────

function scanFile(content) {
  const result = {
    isClientComponent: false,
    defaultExport: null,
    exports: [],
    propsInterface: null,
    hooks: [],
    docstring: null,
  }

  const head = content.substring(0, 200)

  // 'use client'
  result.isClientComponent = /^['"]use client['"]/m.test(head)

  // JSDoc docstring
  const docMatch = content.substring(0, 2000).match(/\/\*\*([\s\S]*?)\*\//)
  if (docMatch) {
    result.docstring = docMatch[1]
      .split('\n')
      .map(l => l.replace(/^\s*\*\s?/, ''))
      .join('\n')
      .trim()
  }

  // Named exports: export function X, export const X, export class X, export type X, export interface X
  const namedRe = /export\s+(?:default\s+)?(?:function|const|let|var|class|type|interface)\s+(\w+)/g
  let m
  while ((m = namedRe.exec(content)) !== null) {
    result.exports.push(m[1])
  }

  // Re-exports: export { X, Y as Z }
  const reExportRe = /export\s*\{([^}]+)\}/g
  while ((m = reExportRe.exec(content)) !== null) {
    const items = m[1].split(',').map(s => {
      const parts = s.trim().split(/\s+as\s+/)
      return parts[parts.length - 1].trim()
    }).filter(Boolean)
    result.exports.push(...items)
  }

  // Default export name
  const defRe = /export\s+default\s+(?:function\s+)?(\w+)/g
  while ((m = defRe.exec(content)) !== null) {
    result.defaultExport = m[1]
  }
  // export { X as default }
  const defAsRe = /export\s*\{(\w+)\s+as\s+default\}/g
  while ((m = defAsRe.exec(content)) !== null) {
    result.defaultExport = m[1]
  }

  // Deduplicate exports
  result.exports = [...new Set(result.exports)]

  // Props interface
  const propsRe = /interface\s+(\w*Props)\s*(?:extends\s+\w+\s*)?\{([^}]*)\}/g
  while ((m = propsRe.exec(content)) !== null) {
    const fields = m[2]
      .split(/[;\n]/)
      .map(f => f.trim())
      .filter(f => f && !f.startsWith('//') && !f.startsWith('/*'))
    result.propsInterface = { name: m[1], fields }
    break // only capture first Props interface
  }

  // Hooks
  const hookRe = /(?:const\s*(?:\{[^}]*\})?\s*=\s*)?(use[A-Z]\w*)\s*\(/g
  const hookSet = new Set()
  while ((m = hookRe.exec(content)) !== null) {
    hookSet.add(m[1])
  }
  result.hooks = [...hookSet]

  return result
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  const files = []
  for (const dir of SCAN_DIRS) {
    files.push(...await walkDir(join(CWD, dir)))
  }

  const modules = {}
  let clientComponents = 0
  let filesWithProps = 0
  const hookUsage = {}

  for (const file of files) {
    const rel = relative(CWD, file).replace(/\\/g, '/')
    const content = await readFile(file, 'utf-8')
    const info = scanFile(content)

    modules[rel] = info

    if (info.isClientComponent) clientComponents++
    if (info.propsInterface) filesWithProps++
    for (const h of info.hooks) {
      hookUsage[h] = (hookUsage[h] || 0) + 1
    }
  }

  const output = {
    generated_at: new Date().toISOString(),
    modules,
    summary: {
      totalFiles: files.length,
      clientComponents,
      filesWithProps,
      hookUsage,
    },
  }

  await mkdir(join(CWD, 'site/guide/architecture'), { recursive: true })
  await writeFile(OUTPUT_PATH, JSON.stringify(output, null, 2) + '\n')
  console.log(`Wrote ${OUTPUT_PATH}`)
  console.log(`  ${files.length} files, ${clientComponents} client components, ${filesWithProps} with props`)
}

main().catch(err => { console.error(err); process.exit(1) })
