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
