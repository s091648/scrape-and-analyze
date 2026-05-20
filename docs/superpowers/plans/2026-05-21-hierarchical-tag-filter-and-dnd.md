# Hierarchical Tag Filter & Drag-and-Drop Tag Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hierarchical group→tag filter to the article filter bar, and allow admins to drag tags between groups on the tags page with a pending-confirmation workflow.

**Architecture:** Feature 1 replaces the flat `MultiSelectPopover` for tags with a new `GroupedTagSelect` component that fetches full tag-group data (via `fetchTagGroups`) and renders collapsible groups. Feature 2 wraps the tags page in a `@dnd-kit/core` `DndContext`; `TagBadge` becomes draggable and `TagGroupCard` becomes a droppable zone; pending moves are tracked at page level and committed (single or batch API call) only after admin confirmation.

**Tech Stack:** React 19, Next.js 16, `@dnd-kit/core`, Vitest + Testing Library (frontend unit tests), FastAPI + SQLAlchemy (backend), pytest (backend unit tests)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/components/features/articles/grouped-tag-select.tsx` | **Create** | Hierarchical tag picker: expandable groups, group-level toggle, search with highlight |
| `frontend/tests/unit/grouped-tag-select.test.tsx` | **Create** | Unit tests for GroupedTagSelect |
| `frontend/components/features/articles/filter-bar.tsx` | **Modify** | Swap tag MultiSelectPopover for GroupedTagSelect; add `useTopic()` |
| `frontend/tests/unit/filter-bar.test.tsx` | **Modify** | Update mocks: `fetchTagGroups` replaces `fetchArticleFilterTags`; add `useTopic` mock |
| `frontend/lib/providers/locales/en.json` | **Modify** | Add `filterBar.noTagsFound`, `tags.pendingChanges`, `tags.confirmMoves`, `tags.discardMoves` |
| `frontend/lib/providers/locales/zh-TW.json` | **Modify** | Same keys in Traditional Chinese |
| `backend/routers/tags.py` | **Modify** | Extend `TagUpdate` with optional `tag_group_name`; update PUT handler; add `POST /tags/batch-move` |
| `backend/tests/test_tags.py` | **Create** | Unit tests for PUT /tags and POST /tags/batch-move |
| `frontend/lib/api/tags.ts` | **Modify** | Add `moveTag(tagId, groupName, token)` and `batchMoveTags(moves, token)` |
| `frontend/app/globals.css` | **Modify** | Add `@keyframes wiggle` and `animate-wiggle` theme entry |
| `frontend/components/features/tags/pending-changes-panel.tsx` | **Create** | Fixed bottom-right panel: pending count + Confirm + Discard buttons |
| `frontend/components/features/tags/tag-group-card.tsx` | **Modify** | `TagBadge` gains `groupId` + `useDraggable`; `TagGroupCard` gains `useDroppable`; `useEffect` syncs internal tags on `group.tags` change; accepts `pendingIncomingTagIds` |
| `frontend/app/tags/page.tsx` | **Modify** | Wrap with `DndContext`; manage `pendingMoves` state; `handleDragEnd`; confirm/discard; pass `pendingIncomingTagIds` per card |

---

## Task 1: Create `GroupedTagSelect` component

**Files:**
- Create: `frontend/components/features/articles/grouped-tag-select.tsx`

- [ ] **Step 1: Write the failing test first**

Create `frontend/tests/unit/grouped-tag-select.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { TagGroupOut } from '@/lib/api/tags'

const groups: TagGroupOut[] = [
  {
    id: 'g1', name: 'research', display_name: 'Research Methods',
    description: null, color_hex: '#6366f1', topic_id: 't1',
    tags: [
      { id: 'tag1', name: 'Transformer', article_count: 10 },
      { id: 'tag2', name: 'Diffusion', article_count: 5 },
    ],
  },
  {
    id: 'g2', name: 'applications', display_name: 'Applications',
    description: null, color_hex: null, topic_id: 't1',
    tags: [
      { id: 'tag3', name: 'Computer Vision', article_count: 8 },
    ],
  },
]

describe('GroupedTagSelect', () => {
  it('renders a trigger button with label', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={[]} onChange={() => {}} />)
    expect(screen.getByRole('button', { name: /tag/i })).toBeInTheDocument()
  })

  it('shows selected count badge when tags are selected', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={['Transformer']} onChange={() => {}} />)
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('clicking group header selects all tags in that group', async () => {
    const onChange = vi.fn()
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={[]} onChange={onChange} />)
    // Open popover
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    // Click group header
    fireEvent.click(screen.getByText('Research Methods'))
    expect(onChange).toHaveBeenCalledWith(['Transformer', 'Diffusion'])
  })

  it('clicking group header when all selected deselects all', async () => {
    const onChange = vi.fn()
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={['Transformer', 'Diffusion']} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.click(screen.getByText('Research Methods'))
    expect(onChange).toHaveBeenCalledWith([])
  })

  it('search filters to matching tag names and shows their group', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={[]} onChange={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: 'Transformer' } })
    // Tag match is visible
    expect(screen.getByText('Transformer')).toBeInTheDocument()
    // Its parent group is visible even though "Research Methods" doesn't match
    expect(screen.getByText('Research Methods')).toBeInTheDocument()
    // Non-matching group is hidden
    expect(screen.queryByText('Applications')).not.toBeInTheDocument()
  })

  it('shows empty text when search has no matches', async () => {
    const { GroupedTagSelect } = await import('@/components/features/articles/grouped-tag-select')
    render(<GroupedTagSelect label="Tag" groups={groups} selected={[]} onChange={() => {}} emptyText="No tags found" />)
    fireEvent.click(screen.getByRole('button', { name: /tag/i }))
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: 'xyznonexistent' } })
    expect(screen.getByText('No tags found')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to confirm it fails**

```
cd frontend && npm run test -- grouped-tag-select
```

Expected: fails with "Cannot find module" or similar.

- [ ] **Step 3: Create the component**

Create `frontend/components/features/articles/grouped-tag-select.tsx`:

```tsx
'use client'
import { useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { TagGroupOut } from '@/lib/api/tags'

interface GroupedTagSelectProps {
  label: string
  groups: TagGroupOut[]
  selected: string[]
  onChange: (val: string[]) => void
  searchPlaceholder?: string
  emptyText?: string
}

function highlight(text: string, query: string) {
  if (!query) return <>{text}</>
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-yellow-100 dark:bg-yellow-900/40 rounded-sm px-0.5 not-italic">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  )
}

export function GroupedTagSelect({
  label, groups, selected, onChange,
  searchPlaceholder = 'Search tags…',
  emptyText = 'No tags found',
}: GroupedTagSelectProps) {
  const [search, setSearch] = useState('')
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())

  const q = search.toLowerCase()

  const visibleGroups = groups.map(g => ({
    ...g,
    matchedTags: search ? g.tags.filter(t => t.name.toLowerCase().includes(q)) : g.tags,
  })).filter(g => !search || g.display_name.toLowerCase().includes(q) || g.matchedTags.length > 0)

  function toggleGroup(g: TagGroupOut) {
    const names = g.tags.map(t => t.name)
    const allSelected = names.every(n => selected.includes(n))
    onChange(allSelected
      ? selected.filter(s => !names.includes(s))
      : [...selected, ...names.filter(n => !selected.includes(n))]
    )
  }

  function toggleTag(name: string) {
    onChange(selected.includes(name) ? selected.filter(s => s !== name) : [...selected, name])
  }

  function toggleExpand(id: string) {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          {label}
          {selected.length > 0 && (
            <Badge variant="secondary" className="h-4 px-1 text-[10px]">{selected.length}</Badge>
          )}
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <div className="px-3 py-2 border-b border-border">
          <input
            className="w-full text-xs bg-transparent outline-none placeholder:text-muted-foreground"
            placeholder={searchPlaceholder}
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="max-h-72 overflow-y-auto py-1">
          {visibleGroups.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">{emptyText}</p>
          )}
          {visibleGroups.map(g => {
            const allSelected = g.tags.every(t => selected.includes(t.name))
            const someSelected = g.tags.some(t => selected.includes(t.name))
            const isExpanded = expandedGroups.has(g.id) || !!search

            return (
              <div key={g.id}>
                {/* Group row */}
                <div className="flex items-center gap-1.5 px-2 py-1.5 hover:bg-muted/50 cursor-pointer">
                  <Checkbox
                    checked={allSelected ? true : someSelected ? 'indeterminate' : false}
                    onCheckedChange={() => toggleGroup(g)}
                    className="h-3.5 w-3.5 shrink-0"
                  />
                  {g.color_hex && (
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: g.color_hex }} />
                  )}
                  <button
                    className="flex-1 text-xs font-medium text-left"
                    onClick={() => toggleGroup(g)}
                  >
                    {highlight(g.display_name, search)}
                  </button>
                  <button
                    className="text-muted-foreground hover:text-foreground shrink-0"
                    onClick={e => { e.stopPropagation(); toggleExpand(g.id) }}
                    aria-label={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded
                      ? <ChevronDown className="h-3 w-3" />
                      : <ChevronRight className="h-3 w-3" />
                    }
                  </button>
                </div>

                {/* Tag rows */}
                {isExpanded && g.matchedTags.map(tag => (
                  <button
                    key={tag.id}
                    className="flex items-center gap-2 pl-7 pr-2 py-1 w-full hover:bg-muted/50 text-left"
                    onClick={() => toggleTag(tag.name)}
                  >
                    <Checkbox
                      checked={selected.includes(tag.name)}
                      onCheckedChange={() => toggleTag(tag.name)}
                      className="h-3 w-3 shrink-0 pointer-events-none"
                    />
                    <span className="text-xs">{highlight(tag.name, search)}</span>
                  </button>
                ))}
              </div>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```
cd frontend && npm run test -- grouped-tag-select
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/features/articles/grouped-tag-select.tsx frontend/tests/unit/grouped-tag-select.test.tsx
git commit -m "✨ [FEAT] add GroupedTagSelect hierarchical tag picker"
```

---

## Task 2: Update `FilterBar` to use `GroupedTagSelect`

**Files:**
- Modify: `frontend/components/features/articles/filter-bar.tsx`

- [ ] **Step 1: Replace tag-related imports and state**

In `filter-bar.tsx`, make these changes:

1. Add imports at the top (after existing imports):
```tsx
import { fetchTagGroups, type TagGroupOut } from '@/lib/api/tags'
import { useTopic } from '@/lib/providers'
import { GroupedTagSelect } from './grouped-tag-select'
```

2. Remove this import line (no longer needed):
```tsx
import { fetchArticleFilterTags } from '@/lib/api/articles'
```
Change it to just:
```tsx
import { fetchArticleFilterSources } from '@/lib/api/articles'
```

3. Inside the `FilterBar` function, add `useTopic()` (after the `useI18n` line):
```tsx
const { selectedTopicId } = useTopic()
```

4. Replace the `tagOptions` state declaration:
```tsx
// Remove:
const [tagOptions, setTagOptions] = useState<string[]>([])
// Add:
const [tagGroups, setTagGroups] = useState<TagGroupOut[]>([])
```

5. Replace the `useEffect` that fetches options:
```tsx
// Remove:
useEffect(() => {
  fetchArticleFilterSources(locale).then(setSourceOptions)
  fetchArticleFilterTags(locale).then(setTagOptions)
}, [locale])

// Add:
useEffect(() => {
  fetchArticleFilterSources(locale).then(setSourceOptions)
  fetchTagGroups(selectedTopicId ?? undefined).then(setTagGroups)
}, [locale, selectedTopicId])
```

6. Replace the `MultiSelectPopover` for tags with `GroupedTagSelect`:
```tsx
// Remove:
<MultiSelectPopover
  label={t('filterBar.tag')}
  options={tagOptions}
  selected={draftTags}
  onChange={setDraftTags}
  searchPlaceholder={`${t('filterBar.search')} ${t('filterBar.tag').toLowerCase()}…`}
/>

// Add:
<GroupedTagSelect
  label={t('filterBar.tag')}
  groups={tagGroups}
  selected={draftTags}
  onChange={setDraftTags}
  searchPlaceholder={`${t('filterBar.search')} ${t('filterBar.tag').toLowerCase()}…`}
  emptyText={t('filterBar.noTagsFound')}
/>
```

- [ ] **Step 2: Run lint to check for errors**

```
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/features/articles/filter-bar.tsx
git commit -m "✨ [FEAT] update FilterBar to use hierarchical tag groups"
```

---

## Task 3: Update `filter-bar.test.tsx`

**Files:**
- Modify: `frontend/tests/unit/filter-bar.test.tsx`

- [ ] **Step 1: Update the test file**

Replace the entire content of `frontend/tests/unit/filter-bar.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { fetchArticleFilterSources } from '@/lib/api/articles'
import { fetchTagGroups } from '@/lib/api/tags'
import type { TagGroupOut } from '@/lib/api/tags'

vi.mock('@/lib/api/articles', () => ({
  fetchArticleFilterSources: vi.fn(),
}))

vi.mock('@/lib/api/tags', () => ({
  fetchTagGroups: vi.fn(),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string) => {
      const map: Record<string, string> = {
        'filterBar.filters': 'Filters',
        'filterBar.source': 'Source',
        'filterBar.tag': 'Tag',
        'filterBar.published': 'Published',
        'filterBar.scraped': 'Scraped',
        'filterBar.search': 'Search',
        'filterBar.any': 'Any',
        'filterBar.after': 'After',
        'filterBar.before': 'Before',
        'filterBar.range': 'Range',
        'filterBar.from': 'From',
        'filterBar.to': 'To',
        'filterBar.clear': 'Clear',
        'filterBar.apply': 'Apply',
        'filterBar.noTagsFound': 'No tags found',
      }
      return map[key] ?? key
    },
  }),
  useTopic: () => ({ selectedTopicId: 'topic-1' }),
}))

const mockTagGroups: TagGroupOut[] = [
  {
    id: 'g1', name: 'research', display_name: 'Research Methods',
    description: null, color_hex: null, topic_id: 'topic-1',
    tags: [{ id: 't1', name: 'AI', article_count: 5 }],
  },
]

const defaultProps = {
  sources: [],
  tags: [],
  publishedAfter: '',
  publishedBefore: '',
  scrapedAfter: '',
  scrapedBefore: '',
  activeFilterCount: 0,
  onApply: vi.fn(),
}

function setupApiMock(sourceOptions = ['rss', 'blog'], tagGroups = mockTagGroups) {
  vi.mocked(fetchArticleFilterSources).mockResolvedValue(sourceOptions)
  vi.mocked(fetchTagGroups).mockResolvedValue(tagGroups)
}

describe('FilterBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupApiMock()
  })

  it('"Filters" toggle button is always rendered', async () => {
    const { FilterBar } = await import('@/components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} />)
    expect(screen.getByRole('button', { name: /filters/i })).toBeInTheDocument()
  })

  it('clicking "Filters" reveals Source and Tag popover triggers', async () => {
    const { FilterBar } = await import('@/components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.getByRole('button', { name: /source/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tag/i })).toBeInTheDocument()
  })

  it('"Clear" button is hidden when activeFilterCount is 0', async () => {
    const { FilterBar } = await import('@/components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument()
  })

  it('"Clear" button is visible when activeFilterCount > 0', async () => {
    const { FilterBar } = await import('@/components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} activeFilterCount={2} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument()
  })

  it('clicking Apply calls onApply with current draft state', async () => {
    const onApply = vi.fn()
    const { FilterBar } = await import('@/components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} sources={['rss']} onApply={onApply} activeFilterCount={1} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /apply/i }))
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ source: ['rss'] }))
  })

  it('"Clear" resets filters and calls onApply with empty values', async () => {
    const onApply = vi.fn()
    const { FilterBar } = await import('@/components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} sources={['rss']} onApply={onApply} activeFilterCount={1} />)
    fireEvent.click(screen.getByRole('button', { name: /filters/i }))
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(onApply).toHaveBeenCalledWith({
      source: [], tag: [], published_after: '', published_before: '', scraped_after: '', scraped_before: '',
    })
  })

  it('fetches source options and tag groups on mount', async () => {
    const { FilterBar } = await import('@/components/features/articles/filter-bar')
    render(<FilterBar {...defaultProps} />)
    await waitFor(() => {
      expect(fetchArticleFilterSources).toHaveBeenCalled()
      expect(fetchTagGroups).toHaveBeenCalledWith('topic-1')
    })
  })
})
```

- [ ] **Step 2: Run tests**

```
cd frontend && npm run test -- filter-bar
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/unit/filter-bar.test.tsx
git commit -m "✅ [FIX] update filter-bar tests for GroupedTagSelect"
```

---

## Task 4: i18n — Feature 1 keys

**Files:**
- Modify: `frontend/lib/providers/locales/en.json`
- Modify: `frontend/lib/providers/locales/zh-TW.json`

- [ ] **Step 1: Add key to `en.json`**

In `frontend/lib/providers/locales/en.json`, inside the `"filterBar"` object, add after `"range": "Range"`:
```json
    "noTagsFound": "No tags found"
```

The `filterBar` block should end like:
```json
  "filterBar": {
    ...
    "range": "Range",
    "noTagsFound": "No tags found"
  },
```

- [ ] **Step 2: Add key to `zh-TW.json`**

In `frontend/lib/providers/locales/zh-TW.json`, inside the `"filterBar"` object, add after `"range": "區間"`:
```json
    "noTagsFound": "找不到標籤"
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/providers/locales/en.json frontend/lib/providers/locales/zh-TW.json
git commit -m "🌐 [FEAT] add i18n keys for hierarchical tag filter"
```

---

## Task 5: Backend — extend `TagUpdate` to support `tag_group_name`

**Files:**
- Modify: `backend/routers/tags.py`

- [ ] **Step 1: Update `TagUpdate` schema**

In `backend/routers/tags.py`, replace the `TagUpdate` class:

```python
# Remove:
class TagUpdate(BaseModel):
    name: str

# Add:
class TagUpdate(BaseModel):
    name: Optional[str] = None
    tag_group_name: Optional[str] = None
```

- [ ] **Step 2: Update the PUT `/tags/{tag_id}` handler**

Replace the `rename_tag` function body:

```python
@router.put("/tags/{tag_id}", response_model=TagOut)
def rename_tag(
    tag_id: UUID,
    body: TagUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag import Tag
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if body.name is not None:
        tag.name = body.name
    if body.tag_group_name is not None:
        tag.tag_group_name = body.tag_group_name
    db.commit()
    db.refresh(tag)
    return TagOut(id=tag.id, name=tag.name, article_count=_tag_article_count(db, tag.id))
```

- [ ] **Step 3: Commit**

```bash
git add backend/routers/tags.py
git commit -m "✨ [FEAT] extend TagUpdate to support tag_group_name move"
```

---

## Task 6: Backend — `POST /tags/batch-move` endpoint

**Files:**
- Modify: `backend/routers/tags.py`

- [ ] **Step 1: Add schemas and endpoint**

In `backend/routers/tags.py`, add after the `TagUpdate` class definition (before the `SuggestionOut` class):

```python
class TagMoveItem(BaseModel):
    tag_id: UUID
    tag_group_name: str


class BatchMoveResult(BaseModel):
    succeeded: List[str]
    failed: List[dict]
```

Then add the endpoint after the existing `DELETE /tags/{tag_id}` handler and before the suggestions endpoints:

```python
@router.post("/tags/batch-move", response_model=BatchMoveResult)
def batch_move_tags(
    body: List[TagMoveItem],
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag import Tag
    succeeded = []
    failed = []
    for item in body:
        try:
            tag = db.query(Tag).filter_by(id=item.tag_id).first()
            if not tag:
                failed.append({"tag_id": str(item.tag_id), "error": "Tag not found"})
                continue
            tag.tag_group_name = item.tag_group_name
            db.commit()
            succeeded.append(str(item.tag_id))
        except Exception as e:
            db.rollback()
            failed.append({"tag_id": str(item.tag_id), "error": str(e)})
    return BatchMoveResult(succeeded=succeeded, failed=failed)
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/tags.py
git commit -m "✨ [FEAT] add POST /tags/batch-move endpoint with partial success"
```

---

## Task 7: Backend unit tests for tag endpoints

**Files:**
- Create: `backend/tests/test_tags.py`

- [ ] **Step 1: Write and run tests**

Create `backend/tests/test_tags.py`:

```python
import uuid
import time
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from jose import jwt

SECRET = "test-secret"


def make_admin_token():
    payload = {"sub": "admin", "role": "admin", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def make_mock_tag(name="Transformer", group="research"):
    tag = MagicMock()
    tag.id = uuid.uuid4()
    tag.name = name
    tag.tag_group_name = group
    return tag


def test_rename_tag_updates_name():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    mock_tag = make_mock_tag()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_tag
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch("backend.routers.tags._tag_article_count", return_value=5):
            response = client.put(
                f"/tags/{mock_tag.id}",
                json={"name": "BERT"},
                headers={"Authorization": f"Bearer {make_admin_token()}"},
            )
        assert response.status_code == 200
        assert mock_tag.name == "BERT"
    finally:
        app.dependency_overrides.clear()


def test_move_tag_updates_group():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    mock_tag = make_mock_tag()
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_tag
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch("backend.routers.tags._tag_article_count", return_value=0):
            response = client.put(
                f"/tags/{mock_tag.id}",
                json={"tag_group_name": "applications"},
                headers={"Authorization": f"Bearer {make_admin_token()}"},
            )
        assert response.status_code == 200
        assert mock_tag.tag_group_name == "applications"
    finally:
        app.dependency_overrides.clear()


def test_batch_move_all_succeed():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    tag1 = make_mock_tag("Tag1", "g1")
    tag2 = make_mock_tag("Tag2", "g1")
    tags_by_id = {str(tag1.id): tag1, str(tag2.id): tag2}

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.side_effect = lambda **kw: MagicMock(
        first=lambda: tags_by_id.get(str(kw.get("id")))
    )
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.post(
            "/tags/batch-move",
            json=[
                {"tag_id": str(tag1.id), "tag_group_name": "g2"},
                {"tag_id": str(tag2.id), "tag_group_name": "g2"},
            ],
            headers={"Authorization": f"Bearer {make_admin_token()}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["succeeded"]) == 2
        assert len(data["failed"]) == 0
    finally:
        app.dependency_overrides.clear()


def test_batch_move_missing_tag_goes_to_failed():
    from backend.main import app
    from backend.database import get_db
    client = TestClient(app)
    missing_id = str(uuid.uuid4())
    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        response = client.post(
            "/tags/batch-move",
            json=[{"tag_id": missing_id, "tag_group_name": "g2"}],
            headers={"Authorization": f"Bearer {make_admin_token()}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["succeeded"]) == 0
        assert data["failed"][0]["tag_id"] == missing_id
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run backend tests**

```
uv run pytest backend/tests/test_tags.py -v
```

Expected: 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_tags.py
git commit -m "✅ [FEAT] add backend unit tests for tag move endpoints"
```

---

## Task 8: Frontend API functions for tag moves

**Files:**
- Modify: `frontend/lib/api/tags.ts`

- [ ] **Step 1: Add `moveTag` and `batchMoveTags`**

In `frontend/lib/api/tags.ts`, add these after the `deleteTag` function:

```typescript
export async function moveTag(tagId: string, tagGroupName: string, token: string): Promise<TagOut> {
  const res = await apiFetch(`/tags/${tagId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ tag_group_name: tagGroupName }),
  })
  if (!res.ok) throw new Error('Failed to move tag')
  return res.json()
}

export interface BatchMoveResult {
  succeeded: string[]
  failed: { tag_id: string; error: string }[]
}

export async function batchMoveTags(
  moves: { tag_id: string; tag_group_name: string }[],
  token: string,
): Promise<BatchMoveResult> {
  const res = await apiFetch('/tags/batch-move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(moves),
  })
  if (!res.ok) throw new Error('Failed to batch move tags')
  return res.json()
}
```

- [ ] **Step 2: Run lint**

```
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/tags.ts
git commit -m "✨ [FEAT] add moveTag and batchMoveTags API functions"
```

---

## Task 9: Install `@dnd-kit/core`

**Files:**
- Modify: `frontend/package.json` (via npm install)

- [ ] **Step 1: Install the package**

```
cd frontend && npm install @dnd-kit/core
```

Expected: `@dnd-kit/core` appears in `package.json` dependencies.

- [ ] **Step 2: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "📦 [FEAT] install @dnd-kit/core for drag-and-drop"
```

---

## Task 10: Add `animate-wiggle` CSS animation

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Add keyframe + theme token**

In `frontend/app/globals.css`, inside the `@theme inline { ... }` block, add before the closing `}`:

```css
  --animate-wiggle: wiggle 0.4s ease-in-out infinite;
```

Then, after the closing `}` of `@theme inline`, add the keyframe definition:

```css
@keyframes wiggle {
  0%, 100% { transform: rotate(-4deg); }
  50% { transform: rotate(4deg); }
}
```

This lets you use `className="animate-wiggle"` via Tailwind v4's `@theme`.

- [ ] **Step 2: Verify the dev server compiles without errors**

Start the dev server briefly:
```
cd frontend && npm run dev
```
Check for CSS compilation errors in the terminal. Then stop with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "✨ [FEAT] add animate-wiggle CSS keyframe"
```

---

## Task 11: Create `PendingChangesPanel` component

**Files:**
- Create: `frontend/components/features/tags/pending-changes-panel.tsx`

- [ ] **Step 1: Create the component**

```tsx
'use client'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/providers'

interface PendingChangesPanelProps {
  count: number
  confirming: boolean
  onConfirm: () => void
  onDiscard: () => void
}

export function PendingChangesPanel({ count, confirming, onConfirm, onDiscard }: PendingChangesPanelProps) {
  const { t } = useI18n()
  return (
    <div className="fixed bottom-4 right-4 z-50 bg-card border border-border rounded-xl shadow-lg px-4 py-3 flex items-center gap-3 animate-in slide-in-from-bottom-2">
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {t('tags.pendingChanges', { count })}
      </span>
      <Button
        variant="ghost" size="sm" className="h-7 text-xs"
        onClick={onDiscard}
        disabled={confirming}
      >
        {t('tags.discardMoves')}
      </Button>
      <Button
        size="sm" className="h-7 text-xs"
        onClick={onConfirm}
        disabled={confirming}
      >
        {confirming ? '…' : t('tags.confirmMoves')}
      </Button>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/features/tags/pending-changes-panel.tsx
git commit -m "✨ [FEAT] add PendingChangesPanel for DnD confirmation"
```

---

## Task 12: Update `tag-group-card.tsx` — droppable + draggable TagBadge

**Files:**
- Modify: `frontend/components/features/tags/tag-group-card.tsx`

- [ ] **Step 1: Add imports**

At the top of `tag-group-card.tsx`, add after the existing imports:

```tsx
import { useDraggable, useDroppable } from '@dnd-kit/core'
import { cn } from '@/lib/utils'
```

Check if `cn` is already imported — if not, add it. (`cn` is in `@/lib/utils`.)

- [ ] **Step 2: Add `groupId` prop to `TagBadge` and make it draggable**

Replace the `TagBadge` component entirely:

```tsx
function TagBadge({
  tag,
  isAdmin,
  token,
  topicId,
  groupId,
  isPending,
  onRenamed,
  onDeleted,
}: {
  tag: TagOut
  isAdmin: boolean
  token?: string
  topicId: string
  groupId: string
  isPending: boolean
  onRenamed: (tagId: string, name: string) => void
  onDeleted: (tagId: string) => void
}) {
  const [open, setOpen] = useState(false)

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: tag.id,
    data: { groupId, tag },
    disabled: !isAdmin,
  })

  return (
    <>
      <button
        ref={setNodeRef}
        {...listeners}
        {...attributes}
        onClick={() => setOpen(true)}
        className={cn(
          'inline-flex items-center gap-1 px-2 py-1 rounded-full border text-xs transition-colors',
          isPending
            ? 'border-green-400 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 animate-wiggle'
            : 'border-border bg-muted/50 hover:bg-muted cursor-pointer',
          isDragging && 'opacity-40',
          isAdmin && 'cursor-grab active:cursor-grabbing',
        )}
      >
        {tag.name}
        <span className="text-muted-foreground tabular-nums [font-variant-ligatures:none]">
          ({tag.article_count})
        </span>
      </button>

      <TagDialog
        tag={tag}
        topicId={topicId}
        isAdmin={isAdmin}
        token={token}
        open={open}
        onOpenChange={setOpen}
        onRenamed={onRenamed}
        onDeleted={onDeleted}
      />
    </>
  )
}
```

- [ ] **Step 3: Update `TagGroupCard` props interface, add droppable + sync effect**

Replace the `Props` interface:

```tsx
interface Props {
  group: TagGroupOut
  isAdmin: boolean
  token?: string
  pendingIncomingTagIds: Set<string>
  onDeleted: (groupId: string) => void
  onTagRenamed: (groupId: string, tagId: string, newName: string) => void
  onTagDeleted: (groupId: string, tagId: string) => void
  onGroupUpdated: (groupId: string, updated: Partial<TagGroupOut>) => void
}
```

Replace the `TagGroupCard` function signature and add sync effect + droppable:

```tsx
export function TagGroupCard({
  group, isAdmin, token, pendingIncomingTagIds,
  onDeleted, onTagRenamed, onTagDeleted, onGroupUpdated,
}: Props) {
  const { t } = useI18n()
  const [tags, setTags] = useState<TagOut[]>(
    [...group.tags].sort((a, b) => b.article_count - a.article_count)
  )
  const [open, setOpen] = useState(true)
  const [editing, setEditing] = useState(false)
  const [localGroup, setLocalGroup] = useState(group)

  // Sync when parent moves a tag in or out (DnD pending moves)
  const tagIdsKey = group.tags.map(t => t.id).join(',')
  useEffect(() => {
    setTags([...group.tags].sort((a, b) => b.article_count - a.article_count))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tagIdsKey])

  const { setNodeRef, isOver } = useDroppable({ id: group.id })

  function handleGroupSaved(updated: Partial<TagGroupOut>) {
    const next = { ...localGroup, ...updated }
    setLocalGroup(next)
    onGroupUpdated(group.id, updated)
    setEditing(false)
  }

  return (
    <div
      ref={setNodeRef}
      className={cn(
        'rounded-xl border border-border bg-card p-5 space-y-3 transition-colors',
        isOver && 'border-primary/50 bg-primary/5',
      )}
    >
```

Keep the rest of the JSX the same, but update the `TagBadge` usage inside `TagGroupCard` to pass the new props:

```tsx
{tags.map(tag => (
  <TagBadge
    key={tag.id}
    tag={tag}
    isAdmin={isAdmin}
    token={token}
    topicId={String(localGroup.topic_id)}
    groupId={String(group.id)}
    isPending={pendingIncomingTagIds.has(tag.id)}
    onRenamed={(tagId, name) => {
      setTags(prev => prev.map(t => t.id === tagId ? { ...t, name } : t))
      onTagRenamed(group.id, tagId, name)
    }}
    onDeleted={tagId => {
      setTags(prev => prev.filter(t => t.id !== tagId))
      onTagDeleted(group.id, tagId)
    }}
  />
))}
```

- [ ] **Step 4: Run lint**

```
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/features/tags/tag-group-card.tsx
git commit -m "✨ [FEAT] make TagBadge draggable and TagGroupCard droppable"
```

---

## Task 13: Wire up DnD context and pending state in `tags/page.tsx`

**Files:**
- Modify: `frontend/app/tags/page.tsx`

- [ ] **Step 1: Add imports**

At the top of `tags/page.tsx`, add after existing imports:

```tsx
import {
  DndContext, DragOverlay, PointerSensor, MouseSensor, TouchSensor,
  useSensor, useSensors,
  type DragEndEvent, type DragStartEvent,
} from '@dnd-kit/core'
import { moveTag, batchMoveTags, type TagOut } from '@/lib/api/tags'
import { PendingChangesPanel } from '@/components/features/tags/pending-changes-panel'
```

Note: `TagOut` is already imported via the `fetchTagGroups` import; adjust if needed to avoid duplicate import.

- [ ] **Step 2: Add pending state and sensor config inside `TagsPage`**

Inside `TagsPage`, after the existing state declarations (`groups`, `suggestions`, etc.), add:

```tsx
interface PendingMove {
  tag: TagOut
  fromGroupId: string
  toGroupId: string
  toGroupName: string
}

const [pendingMoves, setPendingMoves] = useState<Map<string, PendingMove>>(new Map())
const [activeDragTag, setActiveDragTag] = useState<TagOut | null>(null)
const [confirming, setConfirming] = useState(false)

const sensors = useSensors(
  useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
  useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
)
```

- [ ] **Step 3: Add drag handlers**

After the sensors definition, add:

```tsx
function handleDragStart({ active }: DragStartEvent) {
  setActiveDragTag(active.data.current?.tag ?? null)
}

function handleDragEnd({ active, over }: DragEndEvent) {
  setActiveDragTag(null)
  if (!over) return

  const tag: TagOut = active.data.current?.tag
  const fromGroupId: string = active.data.current?.groupId
  const toGroupId = String(over.id)
  if (!tag || fromGroupId === toGroupId) return

  const toGroup = groups.find(g => g.id === toGroupId)
  if (!toGroup) return

  const existingPending = pendingMoves.get(tag.id)
  const originalFromGroupId = existingPending?.fromGroupId ?? fromGroupId

  // Dropped back on original group — cancel this tag's pending move
  if (toGroupId === originalFromGroupId) {
    setGroups(prev => prev.map(g =>
      g.id === fromGroupId ? { ...g, tags: g.tags.filter(t => t.id !== tag.id) } :
      g.id === originalFromGroupId ? { ...g, tags: [...g.tags, tag] } : g
    ))
    setPendingMoves(prev => { const next = new Map(prev); next.delete(tag.id); return next })
    return
  }

  // Move tag visually: remove from current group, add to target group
  setGroups(prev => prev.map(g =>
    g.id === fromGroupId ? { ...g, tags: g.tags.filter(t => t.id !== tag.id) } :
    g.id === toGroupId ? { ...g, tags: [...g.tags, tag] } : g
  ))

  setPendingMoves(prev => new Map(prev).set(tag.id, {
    tag,
    fromGroupId: originalFromGroupId,
    toGroupId,
    toGroupName: toGroup.name,
  }))
}

async function handleConfirm() {
  if (!token || pendingMoves.size === 0) return
  setConfirming(true)
  const moves = [...pendingMoves.values()]

  if (moves.length === 1) {
    const m = moves[0]
    try {
      await moveTag(m.tag.id, m.toGroupName, token)
      setPendingMoves(new Map())
    } catch {
      // leave in pending state for retry
    }
  } else {
    try {
      const result = await batchMoveTags(
        moves.map(m => ({ tag_id: m.tag.id, tag_group_name: m.toGroupName })),
        token,
      )
      const failedIds = new Set(result.failed.map(f => f.tag_id))
      setPendingMoves(prev => {
        const next = new Map(prev)
        result.succeeded.forEach(id => next.delete(id))
        return next
      })
      // Revert failed moves in UI
      if (result.failed.length > 0) {
        setGroups(prev => {
          let next = prev.map(g => ({ ...g, tags: [...g.tags] }))
          for (const m of moves) {
            if (!failedIds.has(m.tag.id)) continue
            next = next
              .map(g => g.id === m.toGroupId ? { ...g, tags: g.tags.filter(t => t.id !== m.tag.id) } : g)
              .map(g => g.id === m.fromGroupId ? { ...g, tags: [...g.tags, m.tag] } : g)
          }
          return next
        })
      }
    } catch {
      // leave all pending for retry
    }
  }
  setConfirming(false)
}

function handleDiscard() {
  const moves = [...pendingMoves.values()]
  setGroups(prev => {
    let next = prev.map(g => ({ ...g, tags: [...g.tags] }))
    for (const m of moves) {
      next = next
        .map(g => g.id === m.toGroupId ? { ...g, tags: g.tags.filter(t => t.id !== m.tag.id) } : g)
        .map(g => g.id === m.fromGroupId ? { ...g, tags: [...g.tags, m.tag] } : g)
    }
    return next
  })
  setPendingMoves(new Map())
}
```

- [ ] **Step 4: Wrap tag group cards with DndContext**

In the JSX, find the section that renders `{groups.map(group => (<TagGroupCard ... />))}`.

1. Wrap the entire `<div className="space-y-4">` block containing the TagGroupCards with `DndContext`:

```tsx
<DndContext
  sensors={sensors}
  onDragStart={handleDragStart}
  onDragEnd={handleDragEnd}
>
  <div className="space-y-4">
    {groups.map(group => {
      const pendingIncomingTagIds = new Set(
        [...pendingMoves.values()]
          .filter(m => m.toGroupId === group.id)
          .map(m => m.tag.id)
      )
      return (
        <TagGroupCard
          key={group.id}
          group={group}
          isAdmin={isAdmin}
          token={token}
          pendingIncomingTagIds={pendingIncomingTagIds}
          onDeleted={groupId => setGroups(prev => prev.filter(g => g.id !== groupId))}
          onTagRenamed={(groupId, tagId, name) => setGroups(prev =>
            prev.map(g => g.id === groupId
              ? { ...g, tags: g.tags.map(t => t.id === tagId ? { ...t, name } : t) }
              : g
            )
          )}
          onTagDeleted={(groupId, tagId) => setGroups(prev =>
            prev.map(g => g.id === groupId
              ? { ...g, tags: g.tags.filter(t => t.id !== tagId) }
              : g
            )
          )}
          onGroupUpdated={(groupId, updated) => setGroups(prev =>
            prev.map(g => g.id === groupId ? { ...g, ...updated } : g)
          )}
        />
      )
    })}
  </div>
  <DragOverlay>
    {activeDragTag && (
      <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-primary bg-card text-xs shadow-md cursor-grabbing">
        {activeDragTag.name}
        <span className="text-muted-foreground tabular-nums">
          ({activeDragTag.article_count})
        </span>
      </div>
    )}
  </DragOverlay>
</DndContext>
```

2. Below the `DndContext` closing tag (but still inside the page's `<>` fragment), add the pending panel:

```tsx
{pendingMoves.size > 0 && (
  <PendingChangesPanel
    count={pendingMoves.size}
    confirming={confirming}
    onConfirm={handleConfirm}
    onDiscard={handleDiscard}
  />
)}
```

- [ ] **Step 5: Run lint**

```
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/tags/page.tsx
git commit -m "✨ [FEAT] wire up DnD context and pending move confirmation in tags page"
```

---

## Task 14: i18n — Feature 2 keys

**Files:**
- Modify: `frontend/lib/providers/locales/en.json`
- Modify: `frontend/lib/providers/locales/zh-TW.json`

- [ ] **Step 1: Add keys to `en.json`**

In the `"tags"` object of `en.json`, add after `"editGroup": "Edit group"`:

```json
    "pendingChanges": "{count} pending change(s)",
    "confirmMoves": "Confirm",
    "discardMoves": "Discard"
```

- [ ] **Step 2: Add keys to `zh-TW.json`**

In the `"tags"` object of `zh-TW.json`, add after `"editGroup": "編輯群組"`:

```json
    "pendingChanges": "{count} 個待確認變更",
    "confirmMoves": "確認",
    "discardMoves": "放棄"
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/providers/locales/en.json frontend/lib/providers/locales/zh-TW.json
git commit -m "🌐 [FEAT] add i18n keys for DnD pending changes panel"
```

---

## Task 15: Final integration check

- [ ] **Step 1: Run all frontend tests**

```
cd frontend && npm run test
```

Expected: all tests pass (including the updated filter-bar tests and new grouped-tag-select tests).

- [ ] **Step 2: Run backend tests**

```
uv run pytest backend/tests/test_tags.py -v
```

Expected: 4 tests pass.

- [ ] **Step 3: Run frontend lint**

```
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 4: Start the dev server and manually verify**

```
cd frontend && npm run dev
```

Verify Feature 1 — article filter bar:
- Open the filter bar, click "Tag"
- Confirm tag groups appear with expand/collapse arrows
- Clicking a group header selects all its tags (badge count updates)
- Typing in search filters tags and highlights matched text in yellow
- Groups without matching tags disappear from search; their parent shows if a tag matches

Verify Feature 2 — tags page (must be logged in as admin):
- Navigate to `/tags`
- Drag a tag badge to a different group card
- Confirm the badge appears in the new group with green background and wiggle animation
- Confirm the pending changes panel appears bottom-right
- Click "Confirm" — badge loses green style, panel disappears
- Drag another tag, then click "Discard" — badge returns to original group

- [ ] **Step 5: Final commit if any last tweaks were needed**

```bash
git add -p  # stage only changed files
git commit -m "✅ [FEAT] final integration polish for tag filter and DnD"
```
