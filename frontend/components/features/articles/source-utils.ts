// Display-only mirror of backend/constants.py SOURCE_CATEGORIES["aggregator"]
export const AGGREGATOR_SOURCES = new Set(['openalex', 'semantic_scholar'])

export function deriveDisplaySource(
  url: string,
  source: string,
  originalSource?: string | null,
): string {
  if (!AGGREGATOR_SOURCES.has(source)) return source
  // Use the server-resolved original_source when available (avoids URL heuristics)
  if (originalSource) return originalSource
  // Fallback: derive from URL hostname for articles scraped before this field existed
  try {
    const { hostname } = new URL(url)
    if (hostname.includes('arxiv.org')) return 'arxiv'
    if (hostname.includes('semanticscholar.org')) return 'semanticscholar'
    if (hostname.includes('biorxiv.org')) return 'biorxiv'
    if (hostname.includes('medrxiv.org')) return 'medrxiv'
    if (hostname.includes('nature.com')) return 'nature'
    if (hostname.includes('springer.com')) return 'springer'
    if (hostname.includes('ieee.org')) return 'ieee'
    if (hostname.includes('acm.org')) return 'acm'
  } catch {}
  return source
}

export function formatViaSource(viaSource: string): string {
  if (viaSource === 'openalex') return 'via OpenAlex'
  if (viaSource === 'semantic_scholar') return 'via Semantic Scholar'
  return `via ${viaSource}`
}

const TITLE_LOWERCASE_WORDS = new Set([
  'a', 'an', 'the',
  'and', 'but', 'or', 'nor', 'for', 'so', 'yet',
  'at', 'by', 'in', 'of', 'on', 'to', 'up', 'as', 'is',
  'via', 'vs', 'per', 'into', 'with', 'from', 'than', 'that',
])

export function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .split(' ')
    .map((word, i) => {
      if (!word) return word
      const base = word.replace(/[^a-zA-Z]/g, '')
      if (i > 0 && TITLE_LOWERCASE_WORDS.has(base)) return word
      return word.charAt(0).toUpperCase() + word.slice(1)
    })
    .join(' ')
}
