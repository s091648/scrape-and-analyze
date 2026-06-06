'use client'
import { useState } from 'react'
import { X, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { useI18n } from '@/lib/providers'

// ── arXiv field definitions (categories handled separately) ───────────────────

const ARXIV_FIELDS = [
  { value: 'ti',  label: 'Title' },
  { value: 'abs', label: 'Abstract' },
  { value: 'au',  label: 'Author' },
  { value: 'all', label: 'All fields' },
  { value: 'co',  label: 'Comment' },
  { value: 'jr',  label: 'Journal Ref' },
  { value: 'rn',  label: 'Report Number' },
] as const

// Curated subset of arXiv category taxonomy
const ARXIV_CATEGORIES = [
  { value: 'cs.AI',          label: 'cs.AI — Artificial Intelligence',       group: 'Computer Science' },
  { value: 'cs.LG',          label: 'cs.LG — Machine Learning',              group: 'Computer Science' },
  { value: 'cs.RO',          label: 'cs.RO — Robotics',                      group: 'Computer Science' },
  { value: 'cs.SY',          label: 'cs.SY — Systems and Control',           group: 'Computer Science' },
  { value: 'cs.NI',          label: 'cs.NI — Networking and Internet',       group: 'Computer Science' },
  { value: 'cs.MA',          label: 'cs.MA — Multi-Agent Systems',           group: 'Computer Science' },
  { value: 'cs.DC',          label: 'cs.DC — Distributed Computing',         group: 'Computer Science' },
  { value: 'cs.AR',          label: 'cs.AR — Hardware Architecture',         group: 'Computer Science' },
  { value: 'cs.ET',          label: 'cs.ET — Emerging Technologies',         group: 'Computer Science' },
  { value: 'cs.GR',          label: 'cs.GR — Graphics',                      group: 'Computer Science' },
  { value: 'cs.SE',          label: 'cs.SE — Software Engineering',          group: 'Computer Science' },
  { value: 'cs.CV',          label: 'cs.CV — Computer Vision',               group: 'Computer Science' },
  { value: 'cs.CR',          label: 'cs.CR — Cryptography and Security',     group: 'Computer Science' },
  { value: 'cs.DB',          label: 'cs.DB — Databases',                     group: 'Computer Science' },
  { value: 'eess.SY',        label: 'eess.SY — Systems and Control',         group: 'EE & Systems' },
  { value: 'eess.SP',        label: 'eess.SP — Signal Processing',           group: 'EE & Systems' },
  { value: 'eess.IV',        label: 'eess.IV — Image and Video Processing',  group: 'EE & Systems' },
  { value: 'physics.app-ph', label: 'physics.app-ph — Applied Physics',      group: 'Physics' },
]

// ── parse / serialize for keyword strings ─────────────────────────────────────

interface ParsedKeyword {
  field: string
  value: string
}

function parseKeyword(raw: string): ParsedKeyword {
  const m = raw.match(/^([a-z_]+):"([^"]+)"$/) ?? raw.match(/^([a-z_]+):(.+)$/)
  if (m) return { field: m[1], value: m[2].trim() }
  return { field: 'all', value: raw }
}

function serializeKeyword(field: string, value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''
  return trimmed.includes(' ') ? `${field}:"${trimmed}"` : `${field}:${trimmed}`
}

function fieldLabel(code: string): string {
  return ARXIV_FIELDS.find(f => f.value === code)?.label ?? code
}

// ── shared types ──────────────────────────────────────────────────────────────

interface Keyword  { id: string; keyword: string }
interface Category { id: string; keyword: string }

// ── component ─────────────────────────────────────────────────────────────────

export function ArxivKeywordManager({
  keywords,
  categories,
  onAddKeyword,
  onDeleteKeyword,
  onAddCategory,
  onDeleteCategory,
}: {
  keywords: Keyword[]
  categories: Category[]
  onAddKeyword: (keyword: string) => Promise<void>
  onDeleteKeyword: (id: string) => Promise<void>
  onAddCategory: (category: string) => Promise<void>
  onDeleteCategory: (id: string) => Promise<void>
}) {
  const { t } = useI18n()
  const [kwField, setKwField] = useState<string>('ti')
  const [kwValue, setKwValue] = useState('')
  const [kwAdding, setKwAdding] = useState(false)

  const [catValue, setCatValue] = useState('')
  const [catAdding, setCatAdding] = useState(false)

  async function handleAddKeyword() {
    const serialized = serializeKeyword(kwField, kwValue)
    if (!serialized) return
    setKwAdding(true)
    await onAddKeyword(serialized)
    setKwValue('')
    setKwAdding(false)
  }

  async function handleAddCategory() {
    if (!catValue) return
    setCatAdding(true)
    await onAddCategory(catValue)
    setCatValue('')
    setCatAdding(false)
  }

  const categoryGroups = ARXIV_CATEGORIES.reduce<Record<string, typeof ARXIV_CATEGORIES>>(
    (acc, c) => { (acc[c.group] ??= []).push(c); return acc },
    {}
  )

  return (
    <div className="space-y-5">

      {/* ── Keywords section ── */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          {t('admin.keywords')}
          <span className="ml-1 font-normal normal-case">— {t('admin.keywordsOrDesc')}</span>
        </p>

        <div className="flex flex-wrap gap-2 min-h-6">
          {keywords.length === 0 && (
            <p className="text-xs text-muted-foreground italic">{t('admin.noKeywordsYet')}</p>
          )}
          {keywords.map(kw => {
            const parsed = parseKeyword(kw.keyword)
            return (
              <span key={kw.id} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-muted text-xs">
                <span className="font-semibold text-muted-foreground">{fieldLabel(parsed.field)}</span>
                <span className="font-mono">{parsed.value}</span>
                <button
                  onClick={() => onDeleteKeyword(kw.id)}
                  className="text-muted-foreground hover:text-foreground transition-colors ml-0.5"
                  aria-label={`Remove ${kw.keyword}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )
          })}
        </div>

        <div className="flex gap-2">
          <NativeSelect
            value={kwField}
            onChange={e => setKwField(e.target.value)}
            className="shrink-0"
          >
            {ARXIV_FIELDS.map(f => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </NativeSelect>
          <input
            className="h-9 px-3 rounded-lg border border-border bg-background text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-ring font-mono"
            placeholder={
              kwField === 'ti'  ? 'e.g. digital twin' :
              kwField === 'abs' ? 'e.g. cyber-physical' :
              kwField === 'au'  ? 'e.g. Smith, John' : 'search term'
            }
            value={kwValue}
            onChange={e => setKwValue(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddKeyword() } }}
          />
          <Button size="sm" variant="outline" onClick={handleAddKeyword} disabled={kwAdding || !kwValue.trim()}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {kwValue.trim() && (
          <p className="text-[10px] text-muted-foreground font-mono">
            {t('admin.storesAs')} <span className="text-foreground">{serializeKeyword(kwField, kwValue)}</span>
          </p>
        )}
      </div>

      {/* ── Categories section ── */}
      <div className="space-y-3 border-t border-border pt-4">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          {t('admin.categories')}
          <span className="ml-1 font-normal normal-case">— {t('admin.categoriesAndDesc')}</span>
        </p>

        <div className="flex flex-wrap gap-2 min-h-6">
          {categories.length === 0 && (
            <p className="text-xs text-muted-foreground italic">{t('admin.noCategories')}</p>
          )}
          {categories.map(cat => (
            <span key={cat.id} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-muted text-xs">
              <span className="font-mono font-semibold">{cat.keyword}</span>
              <button
                onClick={() => onDeleteCategory(cat.id)}
                className="text-muted-foreground hover:text-foreground transition-colors ml-0.5"
                aria-label={`Remove category ${cat.keyword}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>

        <div className="flex gap-2">
          <NativeSelect
            value={catValue}
            onChange={e => setCatValue(e.target.value)}
            className="flex-1"
          >
            <option value="">{t('admin.selectCategory')}</option>
            {Object.entries(categoryGroups).map(([group, cats]) => (
              <optgroup key={group} label={group}>
                {cats.map(c => (
                  <option key={c.value} value={c.value} disabled={categories.some(x => x.keyword === c.value)}>
                    {c.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </NativeSelect>
          <Button size="sm" variant="outline" onClick={handleAddCategory} disabled={catAdding || !catValue}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        {categories.length > 0 && (
          <p className="text-[10px] text-muted-foreground font-mono">
            {t('admin.queryPreview')} <span className="text-foreground">
              ({categories.map(c => `cat:${c.keyword}`).join(' OR ')}) AND ({t('admin.keywords').toLowerCase()}…)
            </span>
          </p>
        )}
      </div>

    </div>
  )
}
