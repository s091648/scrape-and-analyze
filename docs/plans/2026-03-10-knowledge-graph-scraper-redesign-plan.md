# Knowledge Graph Redesign + Frequency-Based Scraper Scheduling — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign knowledge graph visuals (tag nodes, article interaction), migrate scraper frequency to hours-based integer, and replace main.py's argument-based dispatch with DB-driven frequency scheduling.

**Architecture:** Backend changes go DB-first (migration → model → config → main), frontend changes are independent canvas/state rewrites in knowledge-graph.tsx. All backend changes are TDD; frontend is manual verification.

**Tech Stack:** SQLAlchemy, Alembic, PostgreSQL, Python 3.11, Next.js, react-force-graph-2d, TypeScript

---

## Task 1: Update ScraperSetting model

**Files:**
- Modify: `backend/models/scraper_setting.py`

**Step 1: Write failing test**

Add to `tests/unit/test_config.py`:
```python
def test_scraper_setting_frequency_is_integer():
    """ScraperSetting.frequency should be Integer type"""
    from sqlalchemy import Integer
    from backend.models.scraper_setting import ScraperSetting
    col_type = ScraperSetting.__table__.c.frequency.type
    assert isinstance(col_type, Integer)

def test_scraper_setting_has_last_scraped_at():
    """ScraperSetting should have last_scraped_at column"""
    from backend.models.scraper_setting import ScraperSetting
    assert hasattr(ScraperSetting, 'last_scraped_at')
    col = ScraperSetting.__table__.c.last_scraped_at
    assert col.nullable is True
```

Run: `docker compose run --rm app pytest tests/unit/test_config.py::test_scraper_setting_frequency_is_integer tests/unit/test_config.py::test_scraper_setting_has_last_scraped_at -v`
Expected: FAIL

**Step 2: Update the model**

Replace `backend/models/scraper_setting.py` entirely:
```python
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import uuid

ScraperBase = declarative_base()


class ScraperSetting(ScraperBase):
    __tablename__ = 'scraper_settings'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(String(20), nullable=False)   # 'rss' | 'blog' | 'arxiv'
    name = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    frequency = Column(Integer, nullable=False)         # hours between scrapes
    is_active = Column(Boolean, nullable=False, default=True)
    selector_config = Column(JSONB)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
```

**Step 3: Run test to verify pass**

Run: `docker compose run --rm app pytest tests/unit/test_config.py::test_scraper_setting_frequency_is_integer tests/unit/test_config.py::test_scraper_setting_has_last_scraped_at -v`
Expected: PASS

**Step 4: Commit**
```bash
git add backend/models/scraper_setting.py tests/unit/test_config.py
git commit -m "🏗️ [FEAT] update ScraperSetting: frequency → Integer, add last_scraped_at"
```

---

## Task 2: Migration 07 — alter scraper_settings

**Files:**
- Create: `alembic/versions/07_alter_scraper_settings_frequency.py`

**Step 1: Create migration**

```python
"""alter_scraper_settings_frequency

Revision ID: 07_alter_scraper_settings_frequency
Revises: 06_extend_auth_users
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '07_alter_scraper_settings_frequency'
down_revision = '06_extend_auth_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add last_scraped_at
    op.add_column('scraper_settings',
        sa.Column('last_scraped_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add temp integer column, populate, swap
    op.add_column('scraper_settings',
        sa.Column('frequency_hours', sa.Integer(), nullable=True)
    )
    op.execute("UPDATE scraper_settings SET frequency_hours = 24  WHERE frequency = 'daily'")
    op.execute("UPDATE scraper_settings SET frequency_hours = 168 WHERE frequency = 'weekly'")
    op.drop_column('scraper_settings', 'frequency')
    op.alter_column('scraper_settings', 'frequency_hours',
                    new_column_name='frequency', nullable=False)


def downgrade() -> None:
    op.add_column('scraper_settings',
        sa.Column('frequency_str', sa.String(20), nullable=True)
    )
    op.execute("UPDATE scraper_settings SET frequency_str = 'daily'  WHERE frequency = 24")
    op.execute("UPDATE scraper_settings SET frequency_str = 'weekly' WHERE frequency = 168")
    op.drop_column('scraper_settings', 'frequency')
    op.alter_column('scraper_settings', 'frequency_str',
                    new_column_name='frequency', nullable=False)
    op.drop_column('scraper_settings', 'last_scraped_at')
```

**Step 2: Run migration**
```bash
docker compose run --rm app alembic upgrade head
```
Expected: `Running upgrade 06_extend_auth_users -> 07_alter_scraper_settings_frequency`

**Step 3: Verify schema**
```bash
docker compose run --rm app python -c "
from src.database import get_session
from backend.models.scraper_setting import ScraperSetting
s = get_session()
row = s.query(ScraperSetting).first()
print('frequency:', row.frequency, type(row.frequency))
print('last_scraped_at:', row.last_scraped_at)
s.close()
"
```
Expected: frequency is an int (24 or 168), last_scraped_at is None

**Step 4: Commit**
```bash
git add alembic/versions/07_alter_scraper_settings_frequency.py
git commit -m "🏗️ [FEAT] migration 07: frequency String→Integer, add last_scraped_at"
```

---

## Task 3: Migration 08 — seed ArXiv scraper setting

**Files:**
- Create: `alembic/versions/08_seed_arxiv_scraper.py`

**Step 1: Create migration**

```python
"""seed_arxiv_scraper

Revision ID: 08_seed_arxiv_scraper
Revises: 07_alter_scraper_settings_frequency
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '08_seed_arxiv_scraper'
down_revision = '07_alter_scraper_settings_frequency'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO scraper_settings
            (id, source_type, name, url, frequency, is_active, selector_config)
        VALUES (
            gen_random_uuid(),
            'arxiv',
            'arxiv',
            '',
            6,
            true,
            '{"max_results": 30, "days_back": 1}'::jsonb
        )
    """)


def downgrade() -> None:
    op.execute("DELETE FROM scraper_settings WHERE source_type = 'arxiv'")
```

**Step 2: Run migration**
```bash
docker compose run --rm app alembic upgrade head
```
Expected: `Running upgrade 07_... -> 08_seed_arxiv_scraper`

**Step 3: Verify**
```bash
docker compose run --rm app python -c "
from src.database import get_session
from backend.models.scraper_setting import ScraperSetting
s = get_session()
arxiv = s.query(ScraperSetting).filter_by(source_type='arxiv').first()
print(arxiv.name, arxiv.frequency, arxiv.selector_config)
s.close()
"
```
Expected: `arxiv 6 {'max_results': 30, 'days_back': 1}`

**Step 4: Commit**
```bash
git add alembic/versions/08_seed_arxiv_scraper.py
git commit -m "🌱 [FEAT] migration 08: seed arxiv scraper setting (6h frequency)"
```

---

## Task 4: config.py — update get_sources(), add get_sources_due()

**Files:**
- Modify: `src/config.py`
- Modify: `tests/unit/test_config.py`

**Step 1: Write failing tests**

Add to `tests/unit/test_config.py`:
```python
def test_get_sources_filters_by_source_type():
    """get_sources('rss', session) returns only rss sources"""
    from src.config import get_sources
    from unittest.mock import MagicMock

    mock_rss = MagicMock()
    mock_rss.name = 'techcrunch'
    mock_rss.url = 'https://techcrunch.com/feed/'
    mock_rss.source_type = 'rss'
    mock_rss.selector_config = None

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_rss]

    sources = get_sources('rss', session=mock_session)

    assert len(sources) == 1
    assert sources[0]['source'] == 'techcrunch'


def test_get_sources_due_returns_null_last_scraped():
    """get_sources_due returns sources with last_scraped_at IS NULL"""
    from src.config import get_sources_due
    from unittest.mock import MagicMock, patch

    mock_source = MagicMock()
    mock_source.name = 'techcrunch'
    mock_source.url = 'https://techcrunch.com/feed/'
    mock_source.source_type = 'rss'
    mock_source.selector_config = None
    mock_source.last_scraped_at = None

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_source]

    sources = get_sources_due(session=mock_session)
    assert len(sources) == 1
    assert sources[0]['source'] == 'techcrunch'


def test_get_sources_due_result_includes_source_type():
    """get_sources_due result dict includes source_type for dispatcher"""
    from src.config import get_sources_due
    from unittest.mock import MagicMock

    mock_source = MagicMock()
    mock_source.name = 'arxiv'
    mock_source.url = ''
    mock_source.source_type = 'arxiv'
    mock_source.selector_config = {'max_results': 30, 'days_back': 1}
    mock_source.last_scraped_at = None
    mock_source.id = 'some-uuid'

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_source]

    sources = get_sources_due(session=mock_session)
    assert sources[0]['source_type'] == 'arxiv'
    assert sources[0]['id'] == 'some-uuid'
    assert sources[0]['selector_config'] == {'max_results': 30, 'days_back': 1}
```

Run: `docker compose run --rm app pytest tests/unit/test_config.py::test_get_sources_due_returns_null_last_scraped tests/unit/test_config.py::test_get_sources_due_result_includes_source_type -v`
Expected: FAIL

**Step 2: Update config.py**

Replace `get_sources()` and add `get_sources_due()`:
```python
def get_sources(source_type: str, session=None) -> List[Dict[str, Any]]:
    """Get active sources from the database by source_type ('rss', 'blog', 'arxiv')."""
    from backend.models.scraper_setting import ScraperSetting

    own_session = False
    if session is None:
        from src.database import get_session
        session = get_session()
        own_session = True

    try:
        settings = session.query(ScraperSetting).filter(
            ScraperSetting.source_type == source_type,
            ScraperSetting.is_active == True,
        ).all()

        if not settings:
            logger.critical(
                "no_active_sources_found",
                source_type=source_type,
                action="returning_empty_list",
            )
            return []

        result = []
        for s in settings:
            entry = {
                "id": str(s.id),
                "source": s.name,
                "url": s.url,
                "source_type": s.source_type,
                "selector_config": s.selector_config,
            }
            if s.source_type == "blog" and s.selector_config:
                entry["base_url"] = s.url
                entry["selectors"] = s.selector_config
            result.append(entry)
        return result
    finally:
        if own_session:
            session.close()


def get_sources_due(session=None) -> List[Dict[str, Any]]:
    """Return active sources whose last scrape time has exceeded their frequency interval."""
    from backend.models.scraper_setting import ScraperSetting
    from sqlalchemy import or_, text

    own_session = False
    if session is None:
        from src.database import get_session
        session = get_session()
        own_session = True

    try:
        settings = session.query(ScraperSetting).filter(
            ScraperSetting.is_active == True,
        ).filter(
            or_(
                ScraperSetting.last_scraped_at == None,
                text("NOW() - last_scraped_at > frequency * INTERVAL '1 hour'"),
            )
        ).all()

        result = []
        for s in settings:
            entry = {
                "id": str(s.id),
                "source": s.name,
                "url": s.url,
                "source_type": s.source_type,
                "selector_config": s.selector_config or {},
                "frequency": s.frequency,
            }
            if s.source_type == "blog" and s.selector_config:
                entry["base_url"] = s.url
                entry["selectors"] = s.selector_config
            result.append(entry)
        return result
    finally:
        if own_session:
            session.close()
```

**Step 3: Update existing test**

The test `test_get_sources_returns_only_active_daily` now uses `'rss'` not `'daily'`. Rename and update:
```python
# rename test_get_sources_returns_only_active_daily → test_get_sources_filters_by_source_type
# (the new test written in Step 1 already covers this — delete the old one)
```

**Step 4: Run tests**
```bash
docker compose run --rm app pytest tests/unit/test_config.py -v
```
Expected: all PASS

**Step 5: Commit**
```bash
git add src/config.py tests/unit/test_config.py
git commit -m "🏗️ [FEAT] config: get_sources by source_type, add get_sources_due()"
```

---

## Task 5: main.py — frequency-based dispatch

**Files:**
- Modify: `src/main.py`
- Modify: `tests/unit/test_main.py`

**Step 1: Write failing tests**

Add to `tests/unit/test_main.py`:
```python
def test_main_dispatches_rss_scraper_for_rss_source():
    """main() uses RssScraper for source_type='rss'"""
    from unittest.mock import patch, MagicMock
    from src.main import run_scrape_cycle

    source = {
        'id': str(uuid.uuid4()),
        'source': 'techcrunch',
        'url': 'https://techcrunch.com/feed/',
        'source_type': 'rss',
        'selector_config': {},
    }

    with patch('src.main.RssScraper') as MockRss, \
         patch('src.main.get_session') as mock_get_session:
        MockRss.return_value.scrape.return_value = []
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        run_scrape_cycle([source], MagicMock(), 'prompt', str(uuid.uuid4()))

        MockRss.assert_called_once_with(url=source['url'], source=source['source'])


def test_main_dispatches_arxiv_scraper_for_arxiv_source():
    """main() uses ArxivScraper with selector_config params for source_type='arxiv'"""
    from unittest.mock import patch, MagicMock
    from src.main import run_scrape_cycle

    source = {
        'id': str(uuid.uuid4()),
        'source': 'arxiv',
        'url': '',
        'source_type': 'arxiv',
        'selector_config': {'max_results': 30, 'days_back': 1},
    }

    with patch('src.main.ArxivScraper') as MockArxiv, \
         patch('src.main.get_session') as mock_get_session:
        MockArxiv.return_value.scrape.return_value = []
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        run_scrape_cycle([source], MagicMock(), 'prompt', str(uuid.uuid4()))

        MockArxiv.assert_called_once_with(max_results=30, days_back=1)


def test_main_updates_last_scraped_at_after_scrape():
    """run_scrape_cycle updates last_scraped_at in DB after each source"""
    from unittest.mock import patch, MagicMock, call
    from src.main import run_scrape_cycle

    source = {
        'id': 'test-uuid-123',
        'source': 'techcrunch',
        'url': 'https://techcrunch.com/feed/',
        'source_type': 'rss',
        'selector_config': {},
    }

    with patch('src.main.RssScraper') as MockRss, \
         patch('src.main.get_session') as mock_get_session, \
         patch('src.main.text') as mock_text:
        MockRss.return_value.scrape.return_value = []
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        run_scrape_cycle([source], MagicMock(), 'prompt', str(uuid.uuid4()))

        mock_session.execute.assert_called()
        mock_session.commit.assert_called()
```

Run: `docker compose run --rm app pytest tests/unit/test_main.py::test_main_dispatches_rss_scraper_for_rss_source -v`
Expected: FAIL (run_scrape_cycle not defined)

**Step 2: Refactor main.py**

Extract scrape dispatch into `run_scrape_cycle()`, simplify `main()`:

```python
# Replace run_daily_scrape() and run_weekly_scrape() with:

def run_scrape_cycle(sources: list, analyzer, prompt: str, correlation_id: str) -> None:
    """Scrape and analyze all provided sources, update last_scraped_at per source."""
    for source in sources:
        source_type = source['source_type']
        logger.info("scrape_source_start", source=source['source'], source_type=source_type)

        try:
            if source_type == 'rss':
                scraper = RssScraper(url=source['url'], source=source['source'])
            elif source_type == 'blog':
                scraper = BlogScraper(
                    base_url=source['base_url'],
                    source=source['source'],
                    selectors=source['selectors'],
                )
            elif source_type == 'arxiv':
                cfg = source.get('selector_config', {})
                scraper = ArxivScraper(
                    max_results=cfg.get('max_results', 30),
                    days_back=cfg.get('days_back', 1),
                )
            else:
                logger.warning("unknown_source_type_skipped", source_type=source_type)
                continue

            articles = scraper.scrape()
            logger.info("source_scraped", source=source['source'], count=len(articles))

            for article in articles:
                if _shutdown_requested or check_timeout(time.time()):
                    return
                process_article_safe(article, analyzer, prompt, correlation_id)

        except Exception as e:
            logger.error("source_scrape_failed", source=source['source'], error=str(e))
            continue

        # Update last_scraped_at
        session = get_session()
        try:
            session.execute(
                text("UPDATE scraper_settings SET last_scraped_at = NOW() WHERE id = :id"),
                {"id": source['id']}
            )
            session.commit()
        finally:
            session.close()


def main() -> None:
    """Main entry point — frequency-based scrape dispatch."""
    configure_logging()

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("execution_started", correlation_id=correlation_id)

    init_db()

    start_time = time.time()

    try:
        from src.config import get_sources_due
        sources_due = get_sources_due()

        if not sources_due:
            logger.info("no_sources_due")
            return

        logger.info("sources_due_count", count=len(sources_due))

        analyzer = build_analyzer()
        prompt = load_prompt()

        run_scrape_cycle(sources_due, analyzer, prompt, correlation_id)

    except Exception as e:
        logger.error("execution_failed", error=str(e))
        raise
    finally:
        duration = time.time() - start_time
        logger.info("execution_completed", duration_seconds=duration)
```

Also remove `parse_args()` and `run_daily_scrape()` / `run_weekly_scrape()`.

**Step 3: Remove/update stale test**

Delete `test_run_daily_scrape_uses_rss_sources` (no longer exists) from `test_main.py`.

**Step 4: Run tests**
```bash
docker compose run --rm app pytest tests/unit/test_main.py -v
```
Expected: all PASS

**Step 5: Commit**
```bash
git add src/main.py tests/unit/test_main.py
git commit -m "🏗️ [FEAT] main: frequency-based dispatch via get_sources_due, add run_scrape_cycle"
```

---

## Task 6: scrape.py — update --source choices

**Files:**
- Modify: `scripts/scrape.py`

**Step 1: Update `parse_args()` and `_scrape()`**

Change `--source` choices from `['daily', 'weekly', 'arxiv']` to `['rss', 'blog', 'arxiv']`:

```python
parser.add_argument(
    "--source",
    choices=["rss", "blog", "arxiv"],
    required=True,
    help="Source type: rss (feeds from DB), blog (blogs from DB), arxiv",
)
```

Update `_scrape()`:
```python
def _scrape(source: str) -> list:
    articles = []

    if source in ("rss", "blog"):
        from src.config import get_sources
        session = get_session()
        try:
            sources = get_sources(source, session)
        finally:
            session.close()

        for src in sources:
            if source == "rss":
                scraper = RssScraper(url=src["url"], source=src["source"])
            else:
                scraper = BlogScraper(
                    base_url=src["base_url"],
                    source=src["source"],
                    selectors=src["selectors"],
                )
            batch = scraper.scrape()
            articles.extend(batch)
            logger.info("source_scraped", source=src["source"], count=len(batch))

    elif source == "arxiv":
        from src.config import get_sources
        session = get_session()
        try:
            arxiv_sources = get_sources("arxiv", session)
        finally:
            session.close()
        cfg = arxiv_sources[0].get("selector_config", {}) if arxiv_sources else {}
        scraper = ArxivScraper(
            max_results=cfg.get("max_results", 30),
            days_back=cfg.get("days_back", 1),
        )
        articles = scraper.scrape()
        logger.info("source_scraped", source="arxiv", count=len(articles))

    return articles
```

**Step 2: Update Makefile**

In `Makefile`, update the comment:
```makefile
#   make scrape SOURCE=rss
#   make scrape SOURCE=arxiv LIMIT=10
#   make scrape SOURCE=blog NO_ANALYZE=1
```

**Step 3: Verify manually**
```bash
docker compose run --rm job_service python scripts/scrape.py --help
```
Expected: shows `{rss,blog,arxiv}` in choices

**Step 4: Commit**
```bash
git add scripts/scrape.py Makefile
git commit -m "🔧 [FIX] scrape.py: update --source choices to rss/blog/arxiv"
```

---

## Task 7: Knowledge graph — group badge larger + article node smaller

**Files:**
- Modify: `frontend/components/knowledge-graph.tsx`

**Step 1: Update group node canvas — larger article count badge**

In `nodeCanvasObject`, in the `isGroup` (collapsed) branch, find:
```typescript
const badgeFontSize = Math.max(8 / globalScale, 2)
ctx.font = `bold ${badgeFontSize}px sans-serif`
```
Change to:
```typescript
const badgeFontSize = Math.max(14 / globalScale, 4)
ctx.font = `bold ${badgeFontSize}px sans-serif`
```

**Step 2: Update article node canvas — smaller radius, no label**

In the `else` branch (article node), replace the entire block:
```typescript
} else {
  // --- Article node (small dot, no label) ---
  const radius = 4
  ctx.beginPath()
  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
  ctx.fillStyle = '#10b981'
  ctx.fill()
}
```

**Step 3: Add tag node canvas rendering**

Add a new branch before the closing `}` of `nodeCanvasObject`:
```typescript
} else if (node.type === 'tag') {
  // --- Tag node ---
  const radius = 5
  ctx.beginPath()
  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
  ctx.fillStyle = node.color || '#6b7280'
  ctx.globalAlpha = 0.8
  ctx.fill()
  ctx.globalAlpha = 1.0

  const tagFontSize = Math.max(9 / globalScale, 2)
  ctx.font = `${tagFontSize}px sans-serif`
  ctx.fillStyle = '#374151'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  const truncTag = (node.label || '').length > 18
    ? (node.label || '').slice(0, 16) + '…'
    : (node.label || '')
  ctx.fillText(truncTag, node.x, node.y + radius + 2)
}
```

**Step 4: Verify in browser**

Start frontend: `docker compose up frontend`
Navigate to knowledge graph page — group nodes should show larger count number; article nodes should be small green dots without labels.

**Step 5: Commit**
```bash
git add frontend/components/knowledge-graph.tsx
git commit -m "✨ [FEAT] knowledge graph: larger group badge, smaller article nodes, tag node style"
```

---

## Task 8: Knowledge graph — overlay tag nodes + edges on group expand

**Files:**
- Modify: `frontend/components/knowledge-graph.tsx`

**Step 1: Add overlay state**

Add after existing state declarations:
```typescript
const [overlayNodes, setOverlayNodes] = useState<GraphNode[]>([])
const [overlayEdges, setOverlayEdges] = useState<GraphEdge[]>([])
```

**Step 2: Add merged graph data memo**

Add after the `aggregateTags` useMemo:
```typescript
const mergedGraphData = useMemo(() => ({
  nodes: [...graphData.nodes, ...overlayNodes],
  links: [...graphData.edges, ...overlayEdges],
}), [graphData.nodes, graphData.edges, overlayNodes, overlayEdges])
```

**Step 3: Update handleNodeClick to inject overlay**

Replace `handleNodeClick`:
```typescript
function handleNodeClick(node: any) {
  if (node.type === 'group') {
    if (expandedGroupRef.current === node.groupName) {
      // Collapse
      setExpandedGroup(null)
      setGroupData([])
      setOverlayNodes([])
      setOverlayEdges([])
    } else {
      setExpandedGroup(node.groupName)
      setExpandedGroupLabel(node.label)
      setExpandedGroupColor(node.color || '#6b7280')
      setOverlayNodes([])
      setOverlayEdges([])

      apiFetch(`/analyses/graph/group/${encodeURIComponent(node.groupName)}`)
        .then(r => r.json())
        .then((data: GroupArticle[]) => {
          setGroupData(data)

          // Build tag overlay
          const uniqueTags = [...new Set(data.flatMap(a => a.tags))]

          const tagNodes: GraphNode[] = uniqueTags.map(tag => ({
            id: `tag::${node.groupName}::${tag}`,
            type: 'tag' as const,
            label: tag,
            color: node.color || '#6b7280',
            groupName: node.groupName,
          }))

          const tagEdges: GraphEdge[] = [
            // group → tag
            ...uniqueTags.map(tag => ({
              source: node.id,
              target: `tag::${node.groupName}::${tag}`,
            })),
            // tag → article
            ...data.flatMap(article =>
              article.tags.map(tag => ({
                source: `tag::${node.groupName}::${tag}`,
                target: article.articleId,
              }))
            ),
          ]

          setOverlayNodes(tagNodes)
          setOverlayEdges(tagEdges)
        })
    }
  }
  // article node click handled in Task 9
}
```

**Step 4: Wire mergedGraphData to ForceGraph**

Replace `graphData={{ nodes: graphData.nodes, links: graphData.edges }}` with:
```typescript
graphData={mergedGraphData}
```

Also simplify the expanded group canvas object — since tags are now real graph nodes, remove the inner tag rendering from the expanded group canvas:
```typescript
if (isExpanded) {
  // Just show dashed outline + group label
  const outerRadius = 20
  ctx.beginPath()
  ctx.arc(node.x, node.y, outerRadius, 0, 2 * Math.PI)
  ctx.setLineDash([5, 3])
  ctx.strokeStyle = node.color || '#6b7280'
  ctx.lineWidth = 2 / globalScale
  ctx.stroke()
  ctx.setLineDash([])

  const titleFontSize = Math.max(11 / globalScale, 3)
  ctx.font = `bold ${titleFontSize}px sans-serif`
  ctx.fillStyle = node.color || '#6b7280'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'bottom'
  ctx.fillText(node.label, node.x, node.y - outerRadius - 4 / globalScale)
}
```

**Step 5: Verify in browser**

Click a group node — should see tag nodes appear as dots with labels, connected by lines to both the group and to articles.

**Step 6: Commit**
```bash
git add frontend/components/knowledge-graph.tsx
git commit -m "✨ [FEAT] knowledge graph: inject tag overlay nodes+edges on group expand"
```

---

## Task 9: Knowledge graph — article hover/click → right panel + View Full dialog

**Files:**
- Modify: `frontend/components/knowledge-graph.tsx`

**Step 1: Add selected/hovered article state and dialog state**

Add after overlay state:
```typescript
const [selectedArticle, setSelectedArticle] = useState<GroupArticle | null>(null)
const [dialogOpen, setDialogOpen] = useState(false)
const [dialogDetail, setDialogDetail] = useState<any>(null)
const [dialogLoading, setDialogLoading] = useState(false)
```

Add ref for selected article (used in canvas callback):
```typescript
const selectedArticleRef = useRef<GroupArticle | null>(null)
useEffect(() => { selectedArticleRef.current = selectedArticle }, [selectedArticle])
```

**Step 2: Add onNodeHover + article click in handleNodeClick**

Add `onNodeHover` to ForceGraph:
```typescript
onNodeHover={(node: any) => {
  if (node?.type === 'article') {
    const article = groupDataRef.current.find(a => a.articleId === node.id)
    setSelectedArticle(article || null)
  } else if (!node) {
    // only clear if nothing is clicked-selected
    // keep selectedArticle if user clicked an article
  }
}}
```

In `handleNodeClick`, add article branch:
```typescript
} else if (node.type === 'article') {
  const article = groupDataRef.current.find(a => a.articleId === node.id)
  setSelectedArticle(article || null)
}
```

**Step 3: Add openDialog helper**

```typescript
function openArticleDialog(articleId: string) {
  setDialogOpen(true)
  if (!dialogDetail || dialogDetail.id !== articleId) {
    setDialogLoading(true)
    setDialogDetail(null)
    apiFetch(`/articles/${articleId}`)
      .then(r => r.json())
      .then(data => { setDialogDetail(data); setDialogLoading(false) })
      .catch(() => setDialogLoading(false))
  }
}
```

**Step 4: Update right panel JSX**

Replace the right panel `{expandedGroup ? ... : ...}` block:

```tsx
{/* Right panel — 40% */}
<div className="w-[40%] flex flex-col min-h-0">
  {selectedArticle ? (
    /* Article detail view */
    <div className="flex flex-col h-full border border-border rounded-xl bg-card overflow-hidden">
      <div className="flex items-start justify-between px-4 py-3 border-b border-border shrink-0">
        <h3 className="text-sm font-semibold text-foreground leading-snug pr-2">
          {selectedArticle.title}
        </h3>
        <button
          className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => setSelectedArticle(null)}
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
        {selectedArticle.pain_points && (
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Pain Points
            </span>
            <p className="text-xs text-foreground mt-0.5 leading-relaxed">
              {selectedArticle.pain_points}
            </p>
          </div>
        )}
        {selectedArticle.insights && (
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Insights
            </span>
            <p className="text-xs text-foreground mt-0.5 leading-relaxed">
              {selectedArticle.insights}
            </p>
          </div>
        )}
        {selectedArticle.innovations && (
          <div>
            <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Innovations
            </span>
            <p className="text-xs text-foreground mt-0.5 leading-relaxed">
              {selectedArticle.innovations}
            </p>
          </div>
        )}
      </div>
      <div className="px-4 py-3 border-t border-border shrink-0">
        <button
          className="w-full text-xs font-medium text-center py-2 px-3 rounded-lg border border-border hover:bg-muted/40 transition-colors"
          onClick={() => openArticleDialog(selectedArticle.articleId)}
        >
          View Full Article
        </button>
      </div>
    </div>
  ) : expandedGroup ? (
    /* Group detail view (existing behavior) */
    <div className="flex flex-col h-full border border-border rounded-xl bg-card overflow-hidden">
      {/* ... existing group panel JSX unchanged ... */}
    </div>
  ) : (
    <div className="flex-1 flex items-center justify-center border border-dashed border-border rounded-xl text-sm text-muted-foreground">
      Click a group node to explore
    </div>
  )}
</div>
```

**Step 5: Add View Full dialog**

Add imports at top of file:
```typescript
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Globe, Clock } from 'lucide-react'
```

Add dialog JSX after the main `<div>` wrapper (before closing tag):
```tsx
<Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
  <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col gap-0 p-0 overflow-hidden">
    <DialogHeader className="px-6 pt-6 pb-4 border-b border-border">
      <DialogTitle className="text-lg leading-snug pr-6">
        {dialogDetail?.title ?? selectedArticle?.title ?? ''}
      </DialogTitle>
      <div className="flex flex-wrap items-center gap-3 pt-1">
        {dialogDetail?.source && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Globe className="h-3 w-3" />{dialogDetail.source}
          </span>
        )}
        {dialogDetail?.published_at && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            {new Date(dialogDetail.published_at).toLocaleDateString('en-US', {
              month: 'short', day: 'numeric', year: 'numeric'
            })}
          </span>
        )}
      </div>
    </DialogHeader>
    <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">
      {dialogLoading ? (
        <div className="py-8 text-center text-muted-foreground text-sm">Loading…</div>
      ) : dialogDetail ? (
        <div className="space-y-6">
          <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
            {dialogDetail.content}
          </p>
          {dialogDetail.pain_points && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                Pain Points
              </h4>
              <p className="text-sm text-foreground leading-relaxed">{dialogDetail.pain_points}</p>
            </div>
          )}
          {dialogDetail.insights && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                Insights
              </h4>
              <p className="text-sm text-foreground leading-relaxed">{dialogDetail.insights}</p>
            </div>
          )}
          {dialogDetail.innovations && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                Innovations
              </h4>
              <p className="text-sm text-foreground leading-relaxed">{dialogDetail.innovations}</p>
            </div>
          )}
        </div>
      ) : null}
    </div>
  </DialogContent>
</Dialog>
```

**Step 6: Run full test suite**
```bash
docker compose run --rm app pytest tests/ -v --ignore=tests/integration
```
Expected: all pass (backend unaffected by frontend changes)

**Step 7: Verify in browser**

- Hover article node → right panel shows title + pain points + insights
- Click "View Full Article" → dialog opens with full content
- Click X → panel returns to group view or empty state

**Step 8: Final commit**
```bash
git add frontend/components/knowledge-graph.tsx
git commit -m "✨ [FEAT] knowledge graph: article hover/click panel + View Full dialog"
```
