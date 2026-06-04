#!/usr/bin/env node
// Scans specs/ and generates .vitepress/config.js + index.md automatically.
// Run: node scripts/generate-config.mjs  (from site/ directory)
import { readdir, readFile, writeFile } from 'fs/promises'
import { existsSync } from 'fs'
import { join, resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const SPECS_DIR = resolve(__dirname, '../../specs')
const SITE_DIR = resolve(__dirname, '..')
const CONFIG_PATH = join(SITE_DIR, '.vitepress', 'config.js')
const INDEX_PATH = join(SITE_DIR, 'index.md')

// Special-case acronyms when converting kebab-case to Title Case
const WORD_OVERRIDES = {
  llm: 'LLM', api: 'API', url: 'URL', otel: 'OTel',
  sdd: 'SDD', rss: 'RSS', geoip: 'GeoIP', db: 'DB',
}

// Fixed file slots in sidebar display order
const FILE_SLOTS = [
  { file: 'spec.md',                    label: 'Spec' },
  { file: 'plan.md',                    label: 'Plan' },
  { file: 'data-model.md',              label: 'Data Model' },
  { file: 'tasks.md',                   label: 'Tasks' },
  { file: 'research.md',                label: 'Research' },
  { file: 'quickstart.md',              label: 'Quick Start' },
  { file: 'checklists/requirements.md', label: 'Requirements' },
]

function toTitleCase(kebab) {
  return kebab.split('-').map(w => {
    const key = w.toLowerCase()
    return WORD_OVERRIDES[key] ?? (w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
  }).join(' ')
}

// "001-article-collection" → "001 · Article Collection"
function dirToTitle(dirName) {
  const m = dirName.match(/^(\d+)-(.+)$/)
  if (!m) return dirName
  return `${m[1]} · ${toTitleCase(m[2])}`
}

// "llm-service.md" → "Contract: LLM Service"
// "logging-contract.md" → "Contract: Logging"
function contractLabel(filename) {
  const name = filename.replace(/\.md$/, '').replace(/-contract$/, '')
  return `Contract: ${toTitleCase(name)}`
}

// Escape single quotes for YAML single-quoted strings
function yamlSingleQuote(str) {
  return str.replace(/'/g, "''")
}

// Extract the **Input**: value from spec.md, or return null
async function extractDescription(specDir) {
  const specPath = join(specDir, 'spec.md')
  if (!existsSync(specPath)) return null
  const content = await readFile(specPath, 'utf-8')
  for (const line of content.split('\n')) {
    if (line.startsWith('## ')) break
    const m = line.match(/^\*\*Input\*\*:\s*(.+)/)
    if (m) {
      let desc = m[1].trim()
      desc = desc.replace(/^User description:\s*/i, '')  // strip "User description:" prefix
      desc = desc.replace(/^["']|["']$/g, '').trim()      // strip surrounding quotes
      return desc
    }
  }
  return null
}

async function getSpecDirs() {
  const entries = await readdir(SPECS_DIR, { withFileTypes: true })
  return entries
    .filter(e => e.isDirectory() && /^\d+-.+/.test(e.name))
    .map(e => e.name)
    .sort()
}

async function buildSpecs(dirs) {
  return Promise.all(dirs.map(async (dirName, i) => {
    const dirPath = join(SPECS_DIR, dirName)
    const title = dirToTitle(dirName)
    const slug = `/specs/${dirName}`

    // Standard file slots
    const items = []
    for (const { file, label } of FILE_SLOTS) {
      if (existsSync(join(dirPath, file))) {
        items.push({ text: label, link: `${slug}/${file.replace(/\.md$/, '')}` })
      }
    }

    // Contract files (sorted alphabetically)
    const contractsDir = join(dirPath, 'contracts')
    if (existsSync(contractsDir)) {
      const files = (await readdir(contractsDir)).filter(f => f.endsWith('.md')).sort()
      for (const f of files) {
        items.push({ text: contractLabel(f), link: `${slug}/contracts/${f.replace(/\.md$/, '')}` })
      }
    }

    const description = await extractDescription(dirPath)
    return { title, slug, items, description, isFirst: i === 0 }
  }))
}

function renderConfigJs(specs) {
  const firstLink = specs[0]?.items[0]?.link ?? '/specs'

  const sidebar = specs.map(s => {
    const items = s.items.map(item =>
      `          { text: '${item.text}', link: '${item.link}' },`
    ).join('\n')
    return `      {
        text: '${s.title}',
        collapsed: ${s.isFirst ? 'false' : 'true'},
        items: [
${items}
        ],
      },`
  }).join('\n')

  return `import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Scrape Analyzer',
  description: 'Speckit SDD specification documentation',
  base: process.env.VITEPRESS_BASE || '/',
  ignoreDeadLinks: [/localhost/, /^\\.?\\/?research\\/?$/],
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Speckit Guide', link: '/guide/speckit' },
      { text: 'Codespaces', link: '/guide/codespaces' },
      { text: 'Constitution', link: '/constitution' },
      { text: 'Specs', link: '${firstLink}' },
    ],
    sidebar: [
      {
        text: 'Project',
        items: [
          { text: 'Speckit SDD Guide', link: '/guide/speckit' },
          { text: 'Codespaces 開發環境', link: '/guide/codespaces' },
          { text: 'Constitution', link: '/constitution' },
        ],
      },
${sidebar}
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/s091648/scrape-and-analyze' },
    ],
    search: {
      provider: 'local',
    },
    outline: {
      level: [2, 3],
    },
  },
})
`
}

function renderIndexMd(specs) {
  const firstLink = specs[0]?.items[0]?.link ?? '/specs'

  const features = specs.map(s => {
    const rawDesc = s.description ?? `Feature specification for ${s.title.replace(/^\d+ · /, '')}`
    const desc = yamlSingleQuote(rawDesc)
    const link = s.items[0]?.link ?? s.slug
    return `  - title: '${s.title}'
    details: '${desc}'
    link: '${link}'`
  }).join('\n')

  return `---
layout: home

hero:
  name: Scrape Analyzer
  text: Specification Documentation
  tagline: SDD artifacts — specs, plans, data models, and interface contracts for all ${specs.length} features
  actions:
    - theme: brand
      text: Speckit SDD Guide
      link: /guide/speckit
    - theme: alt
      text: Project Constitution
      link: /constitution
    - theme: alt
      text: Browse Specs
      link: ${firstLink}

features:
${features}
---
`
}

async function main() {
  console.log(`Scanning: ${SPECS_DIR}`)
  const dirs = await getSpecDirs()
  console.log(`Found ${dirs.length} spec(s): ${dirs.join(', ')}`)

  const specs = await buildSpecs(dirs)

  await writeFile(CONFIG_PATH, renderConfigJs(specs), 'utf-8')
  console.log(`Written: ${CONFIG_PATH}`)

  await writeFile(INDEX_PATH, renderIndexMd(specs), 'utf-8')
  console.log(`Written: ${INDEX_PATH}`)

  console.log('Done.')
}

main().catch(e => { console.error(e); process.exit(1) })
