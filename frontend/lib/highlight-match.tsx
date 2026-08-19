/** Wraps the first occurrence of `query` anywhere within `text` (case-insensitive, not
 * just a prefix match) in a <mark>. Shared by grouped-tag-select.tsx and
 * autocomplete-dropdown.tsx — extracted rather than duplicated (023-article-search). */
export function highlightMatch(text: string, query: string) {
  if (!query) return <>{text}</>
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-transparent text-red-600 dark:text-red-400 font-bold not-italic">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  )
}
