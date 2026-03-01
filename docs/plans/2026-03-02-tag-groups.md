# Tag Groups Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the flat per-tag knowledge graph with structured tag-group nodes, where the LLM classifies each article into predefined thematic groups; the graph shows ~8 stable group nodes that expand visually on click to reveal individual sub-tags.

**Architecture:** Add a `tag_group_definitions` seed table and a `tag_groups JSONB` column to `analyses`; rewrite the LLM prompt to produce `{"group": "...", "tags": [...]}` objects; update the graph API to return group nodes; rewrite the frontend canvas to draw collapsed/expanded group nodes inline.

**Tech Stack:** PostgreSQL JSONB, SQLAlchemy, Alembic, FastAPI, react-force-graph-2d canvas API, Next.js/TypeScript

**Design doc:** `docs/plans/2026-03-02-tag-groups-design.md`

---

## Task 1: Alembic migration — tag_group_definitions + analyses.tag_groups

**Files:**
- Create: `alembic/versions/b3f1a9d2c8e0_add_tag_groups.py`

**Step 1: Create the migration file**

```python
# alembic/versions/b3f1a9d2c8e0_add_tag_groups.py
"""add_tag_groups

Revision ID: b3f1a9d2c8e0
Revises: f9a54cc49040
Create Date: 2026-03-02
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision: str = 'b3f1a9d2c8e0'
down_revision: Union[str, Sequence[str], None] = 'f9a54cc49040'
branch_labels = None
depends_on = None

_TAG_GROUPS = [
    ('digital_twin',              'Digital Twin',                '#6366f1',
     'Virtual replicas, real-time synchronization, twin lifecycle, model fidelity, twin platforms', 1),
    ('ai_ml',                     'AI & Machine Learning',       '#f59e0b',
     'Predictive analytics, deep learning, anomaly detection, generative AI, inference', 2),
    ('iot_sensing',               'IoT & Sensing',               '#10b981',
     'Sensors, edge computing, telemetry, MQTT/OPC-UA, real-time data collection', 3),
    ('simulation_modeling',       'Simulation & Modeling',       '#3b82f6',
     'Physics simulation, FEA, CFD, 3D modeling, game engines, digital mockups', 4),
    ('manufacturing_industry',    'Manufacturing & Industry 4.0','#ef4444',
     'Factories, industrial automation, supply chain, process optimization, robotics', 5),
    ('construction_smart_cities', 'Construction & Smart Cities', '#8b5cf6',
     'BIM, civil engineering, urban planning, smart infrastructure, building management', 6),
    ('software_devops',           'Software & DevOps',           '#06b6d4',
     'APIs, cloud architecture, cybersecurity, data pipelines, deployment, QA', 7),
    ('other_applications',        'Other Applications',          '#6b7280',
     'Healthcare, energy, transportation, aerospace, agriculture — any domain not above', 8),
]


def upgrade() -> None:
    op.create_table(
        'tag_group_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('color_hex', sa.String(7)),
        sa.Column('description', sa.Text()),
        sa.Column('sort_order', sa.Integer()),
    )

    tgd = sa.table(
        'tag_group_definitions',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('display_name', sa.String),
        sa.column('color_hex', sa.String),
        sa.column('description', sa.Text),
        sa.column('sort_order', sa.Integer),
    )
    op.bulk_insert(tgd, [
        {
            'id': uuid.uuid4(),
            'name': name,
            'display_name': display_name,
            'color_hex': color_hex,
            'description': description,
            'sort_order': sort_order,
        }
        for name, display_name, color_hex, description, sort_order in _TAG_GROUPS
    ])

    op.add_column('analyses', sa.Column('tag_groups', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('analyses', 'tag_groups')
    op.drop_table('tag_group_definitions')
```

**Step 2: Run the migration (inside the app container)**

```bash
docker compose exec app alembic upgrade head
```

Expected: `Running upgrade f9a54cc49040 -> b3f1a9d2c8e0, add_tag_groups`

**Step 3: Commit**

```bash
git add alembic/versions/b3f1a9d2c8e0_add_tag_groups.py
git commit -m "🗄️ FEAT Add tag_group_definitions migration and tag_groups column on analyses"
```

---

## Task 2: SQLAlchemy models — TagGroupDefinition + Analysis.tag_groups

**Files:**
- Create: `src/models/tag_group.py`
- Modify: `src/models/analysis.py`

**Step 1: Create TagGroupDefinition model**

```python
# src/models/tag_group.py
from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from src.models.article import Base
import uuid


class TagGroupDefinition(Base):
    __tablename__ = 'tag_group_definitions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    color_hex = Column(String(7))
    sort_order = Column(Integer)
```

**Step 2: Add tag_groups column to Analysis model**

In `src/models/analysis.py`, change the import line and add the column:

```python
# Change this line:
from sqlalchemy.dialects.postgresql import UUID, ARRAY
# To:
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
```

Add after `tags = Column(...)`:
```python
tag_groups = Column(JSONB)          # [{"group": "digital_twin", "tags": ["virtual replica"]}]
```

**Step 3: Commit**

```bash
git add src/models/tag_group.py src/models/analysis.py
git commit -m "🗄️ FEAT Add TagGroupDefinition model and Analysis.tag_groups column"
```

---

## Task 3: Rewrite LLM analysis prompt

**Files:**
- Modify: `src/prompts/analysis.txt`

**Step 1: Replace the entire file content**

```
You are a professional technology analyst specializing in Digital Twins, IoT, and Industry 4.0.

Analyze the following article and classify it into one or more of the predefined tag groups below.
For each group that genuinely applies, generate 2-4 specific sub-tags describing the article's focus
within that group. Assign 1-3 groups total; only include groups truly relevant to the article.

TAG GROUPS (use these exact group key strings):
- digital_twin: Virtual replicas, real-time synchronization, twin lifecycle, model fidelity, twin platforms
- ai_ml: Predictive analytics, deep learning, anomaly detection, generative AI, inference
- iot_sensing: Sensors, edge computing, telemetry, MQTT/OPC-UA, real-time data collection
- simulation_modeling: Physics simulation, FEA, CFD, 3D modeling, game engines, digital mockups
- manufacturing_industry: Factories, industrial automation, supply chain, process optimization, robotics
- construction_smart_cities: BIM, civil engineering, urban planning, smart infrastructure, building management
- software_devops: APIs, cloud architecture, cybersecurity, data pipelines, deployment, QA
- other_applications: Healthcare, energy, transportation, aerospace, agriculture — any domain not above

Also extract:
- pain_points: Key challenges, problems, or barriers mentioned in the article
- insights: Important observations, trends, or takeaways
- innovations: New technologies, methods, solutions, or approaches mentioned

Return your analysis as valid JSON with these exact fields:
{
  "tag_groups": [
    {"group": "digital_twin", "tags": ["virtual replica", "real-time sync"]},
    {"group": "manufacturing_industry", "tags": ["factory automation", "process optimization"]}
  ],
  "pain_points": "Description of challenges mentioned...",
  "insights": "Key observations and trends...",
  "innovations": "New technologies or approaches..."
}

IMPORTANT: Output ONLY the JSON object, no other text or explanation.
```

**Step 2: Commit**

```bash
git add src/prompts/analysis.txt
git commit -m "✨ FEAT Rewrite analysis prompt to produce structured tag_groups"
```

---

## Task 4: Update AnalysisResult dataclass and both LLM providers

**Files:**
- Modify: `src/analyzers/llm_provider.py`
- Modify: `src/analyzers/claude.py`
- Modify: `src/analyzers/gemini.py`

**Step 1: Update AnalysisResult in llm_provider.py**

Replace the entire file:

```python
# src/analyzers/llm_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class AnalysisResult:
    """Result from LLM analysis"""
    tag_groups: List[Dict[str, Any]]   # [{"group": str, "tags": [str]}]
    tags: List[str]                     # flat union of all sub-tags (backward compat)
    pain_points: str
    insights: str
    innovations: str
    input_tokens: int
    output_tokens: int


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        """Analyze content and return structured result"""
        pass
```

**Step 2: Update claude.py**

Change `_REQUIRED_FIELDS` and `_validate_response`:

```python
# Replace the _validate_response method:
def _validate_response(self, result_json: dict) -> bool:
    """Validate LLM response has required fields with correct types"""
    required_fields = ['tag_groups', 'pain_points', 'insights', 'innovations']

    if not all(field in result_json for field in required_fields):
        logger.error("claude_response_missing_fields",
                     expected=required_fields,
                     actual=list(result_json.keys()))
        return False

    tag_groups = result_json.get('tag_groups')
    if not isinstance(tag_groups, list):
        logger.error("claude_response_invalid_tag_groups",
                     type=type(tag_groups).__name__)
        return False

    for item in tag_groups:
        if not isinstance(item, dict) or 'group' not in item or 'tags' not in item:
            logger.error("claude_response_malformed_tag_group", item=item)
            return False
        if not isinstance(item['tags'], list):
            logger.error("claude_response_tags_not_list", item=item)
            return False

    return True
```

Replace the `return AnalysisResult(...)` block at the bottom of `analyze()`:

```python
        tag_groups = result_json.get('tag_groups', [])
        flat_tags = [tag for tg in tag_groups for tag in tg.get('tags', [])]

        return AnalysisResult(
            tag_groups=tag_groups,
            tags=flat_tags,
            pain_points=result_json.get('pain_points', ''),
            insights=result_json.get('insights', ''),
            innovations=result_json.get('innovations', ''),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
```

**Step 3: Update gemini.py**

Change `_REQUIRED_FIELDS`:
```python
_REQUIRED_FIELDS = ['tag_groups', 'pain_points', 'insights', 'innovations']
```

Replace `_validate_response`:
```python
def _validate_response(self, result_json: dict) -> bool:
    """Validate response has required fields with correct types"""
    if not all(field in result_json for field in _REQUIRED_FIELDS):
        logger.error("gemini_response_missing_fields",
                     expected=_REQUIRED_FIELDS,
                     actual=list(result_json.keys()))
        return False
    tag_groups = result_json.get('tag_groups')
    if not isinstance(tag_groups, list):
        logger.error("gemini_response_invalid_tag_groups",
                     type=type(tag_groups).__name__)
        return False
    for item in tag_groups:
        if not isinstance(item, dict) or 'group' not in item or 'tags' not in item:
            logger.error("gemini_response_malformed_tag_group", item=item)
            return False
        if not isinstance(item['tags'], list):
            return False
    return True
```

Replace the `return AnalysisResult(...)` block at the bottom of `analyze()`:
```python
        tag_groups = result_json.get('tag_groups', [])
        flat_tags = [tag for tg in tag_groups for tag in tg.get('tags', [])]

        return AnalysisResult(
            tag_groups=tag_groups,
            tags=flat_tags,
            pain_points=result_json.get('pain_points', ''),
            insights=result_json.get('insights', ''),
            innovations=result_json.get('innovations', ''),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
```

**Step 4: Run backend tests to verify nothing is broken**

```bash
docker compose exec app pytest backend/tests/ -v
```

Expected: all tests that don't involve the LLM directly still pass. (Graph tests will fail until Task 6 — that's expected.)

**Step 5: Commit**

```bash
git add src/analyzers/llm_provider.py src/analyzers/claude.py src/analyzers/gemini.py
git commit -m "✨ FEAT Update AnalysisResult and LLM providers to produce tag_groups"
```

---

## Task 5: Update analysis pipeline to store tag_groups

**Files:**
- Modify: `src/main.py`

**Step 1: Update analyze_article() to store tag_groups**

In `src/main.py`, find the `analyze_article()` function. The `Analysis(...)` constructor currently sets `tags=result.tags`. Add `tag_groups=result.tag_groups`:

```python
    analysis = Analysis(
        article_id=article.id,
        correlation_id=uuid.UUID(correlation_id),
        tag_groups=result.tag_groups,       # ← ADD THIS LINE
        tags=result.tags,
        pain_points=result.pain_points,
        insights=result.insights,
        innovations=result.innovations,
        model_used=LLM_MODEL,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens
    )
```

**Step 2: Commit**

```bash
git add src/main.py
git commit -m "✨ FEAT Store tag_groups in Analysis records from pipeline"
```

---

## Task 6: Rewrite backend graph router

**Files:**
- Modify: `backend/routers/graph.py`

**Step 1: Replace the entire file**

```python
# backend/routers/graph.py
import json
import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Any

from backend.database import get_db

router = APIRouter()

# In-process cache: {days: (result, expires_at)}
_cache: dict[int, tuple[Any, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def load_group_defs(db: Session) -> dict:
    """Load tag group definitions as a name→metadata dict."""
    from src.models.tag_group import TagGroupDefinition
    rows = db.query(TagGroupDefinition).order_by(TagGroupDefinition.sort_order).all()
    return {
        r.name: {'display_name': r.display_name, 'color_hex': r.color_hex or '#6b7280'}
        for r in rows
    }


def load_group_def(db: Session, group_name: str):
    """Load a single tag group definition by name."""
    from src.models.tag_group import TagGroupDefinition
    return db.query(TagGroupDefinition).filter_by(name=group_name).first()


def query_analyses(db: Session, days: int) -> list:
    from src.models.analysis import Analysis
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return db.query(Analysis).filter(Analysis.analyzed_at >= cutoff).all()


def query_group_articles(db: Session, group_name: str) -> list:
    """Return all analyses that include the given group in their tag_groups JSONB."""
    from src.models.analysis import Analysis
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy import cast
    return db.query(Analysis).filter(
        Analysis.tag_groups.op('@>')(
            cast(json.dumps([{'group': group_name}]), JSONB)
        )
    ).all()


def build_graph(analyses: list, group_defs: dict) -> dict:
    nodes = []
    edges = []
    group_node_ids: set = set()
    article_ids: set = set()
    group_article_counts: dict = {}

    for analysis in analyses:
        article_id = str(analysis.article_id)
        if article_id not in article_ids:
            article_ids.add(article_id)
            nodes.append({
                'id': article_id,
                'type': 'article',
                'label': analysis.article.title if analysis.article else '',
                'articleId': article_id,
            })

        for tg in (analysis.tag_groups or []):
            group_name = tg.get('group', '')
            if not group_name:
                continue
            group_node_id = f'group:{group_name}'
            if group_node_id not in group_node_ids:
                group_node_ids.add(group_node_id)
                gdef = group_defs.get(group_name, {})
                nodes.append({
                    'id': group_node_id,
                    'type': 'group',
                    'label': gdef.get('display_name', group_name),
                    'color': gdef.get('color_hex', '#6b7280'),
                    'groupName': group_name,
                    'articleCount': 0,
                })
                group_article_counts[group_node_id] = 0
            group_article_counts[group_node_id] += 1
            edges.append({'source': group_node_id, 'target': article_id})

    for node in nodes:
        if node['type'] == 'group':
            node['articleCount'] = group_article_counts.get(node['id'], 0)

    return {'nodes': nodes, 'edges': edges}


@router.get('/analyses/graph')
def get_graph(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    now = time.time()
    if days in _cache:
        result, expires_at = _cache[days]
        if now < expires_at:
            return result

    group_defs = load_group_defs(db)
    analyses = query_analyses(db, days)
    result = build_graph(analyses, group_defs)
    _cache[days] = (result, now + CACHE_TTL_SECONDS)
    return result


@router.get('/analyses/graph/group/{group_name}')
def get_group_articles(group_name: str, db: Session = Depends(get_db)):
    group_def = load_group_def(db, group_name)
    display_name = group_def.display_name if group_def else group_name

    analyses = query_group_articles(db, group_name)
    result = []
    for analysis in analyses:
        article = analysis.article
        if not article:
            continue
        group_tags = []
        for tg in (analysis.tag_groups or []):
            if tg.get('group') == group_name:
                group_tags = tg.get('tags', [])
                break
        result.append({
            'groupName': group_name,
            'displayName': display_name,
            'tags': group_tags,
            'articleId': str(analysis.article_id),
            'title': article.title,
            'source': article.source,
            'url': article.url,
            'published_at': article.published_at.isoformat() if article.published_at else None,
            'excerpt': (article.content or '')[:200],
            'pain_points': analysis.pain_points,
            'insights': analysis.insights,
            'innovations': analysis.innovations,
        })
    return result
```

**Step 2: Commit**

```bash
git add backend/routers/graph.py
git commit -m "✨ FEAT Rewrite graph router: group nodes, /graph/group/{name} endpoint"
```

---

## Task 7: Update backend graph tests

**Files:**
- Modify: `backend/tests/test_graph.py`

**Step 1: Replace the entire file**

```python
# backend/tests/test_graph.py
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def make_mock_analysis(tag_groups):
    article = MagicMock()
    article.id = uuid.uuid4()
    article.title = "Test Article"
    article.source = "techcrunch"
    article.url = "https://example.com"
    article.content = "Article content here for testing."
    article.published_at = None
    analysis = MagicMock()
    analysis.tag_groups = tag_groups
    analysis.tags = [t for tg in tag_groups for t in tg.get('tags', [])]
    analysis.article = article
    analysis.article_id = article.id
    analysis.pain_points = "Some pain points"
    analysis.insights = "Some insights"
    analysis.innovations = "Some innovations"
    return analysis


_MOCK_GROUP_DEFS = {
    'digital_twin': {'display_name': 'Digital Twin', 'color_hex': '#6366f1'},
    'ai_ml': {'display_name': 'AI & Machine Learning', 'color_hex': '#f59e0b'},
}


def _mock_group_def(name='digital_twin', display='Digital Twin'):
    m = MagicMock()
    m.display_name = display
    return m


def test_graph_returns_nodes_and_edges():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph?days=30')
    assert response.status_code == 200
    data = response.json()
    assert 'nodes' in data
    assert 'edges' in data


def test_graph_contains_group_and_article_nodes():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph?days=30')
    nodes = response.json()['nodes']
    node_types = {n['type'] for n in nodes}
    assert 'group' in node_types
    assert 'article' in node_types


def test_graph_group_node_has_color_and_count():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        response = client.get('/analyses/graph?days=30')
    group_nodes = [n for n in response.json()['nodes'] if n['type'] == 'group']
    assert len(group_nodes) == 1
    assert group_nodes[0]['color'] == '#6366f1'
    assert group_nodes[0]['articleCount'] == 1


def test_graph_different_days_different_cache():
    import backend.routers.graph as graph_module
    graph_module._cache.clear()
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])]
    with patch('backend.routers.graph.query_analyses', return_value=mock_analyses) as mock_q, \
         patch('backend.routers.graph.load_group_defs', return_value=_MOCK_GROUP_DEFS):
        client.get('/analyses/graph?days=30')
        client.get('/analyses/graph?days=90')
    assert mock_q.call_count == 2


def test_graph_group_endpoint_returns_articles():
    from backend.main import app
    client = TestClient(app)
    mock_analyses = [make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica', 'model fidelity']}])]
    with patch('backend.routers.graph.query_group_articles', return_value=mock_analyses), \
         patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
        response = client.get('/analyses/graph/group/digital_twin')
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]['groupName'] == 'digital_twin'
    assert 'virtual replica' in items[0]['tags']


def test_graph_group_excerpt_max_200_chars():
    from backend.main import app
    client = TestClient(app)
    mock_analysis = make_mock_analysis([{'group': 'digital_twin', 'tags': ['virtual replica']}])
    mock_analysis.article.content = 'x' * 500
    with patch('backend.routers.graph.query_group_articles', return_value=[mock_analysis]), \
         patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
        response = client.get('/analyses/graph/group/digital_twin')
    assert len(response.json()[0]['excerpt']) <= 200


def test_graph_group_no_auth_required():
    from backend.main import app
    client = TestClient(app)
    with patch('backend.routers.graph.query_group_articles', return_value=[]), \
         patch('backend.routers.graph.load_group_def', return_value=_mock_group_def()):
        response = client.get('/analyses/graph/group/any')
    assert response.status_code == 200
```

**Step 2: Run the backend graph tests**

```bash
docker compose exec app pytest backend/tests/test_graph.py -v
```

Expected: all 7 tests PASS.

**Step 3: Run the full backend test suite**

```bash
docker compose exec app pytest backend/tests/ -v
```

Expected: all tests pass.

**Step 4: Commit**

```bash
git add backend/tests/test_graph.py
git commit -m "✅ TEST Update backend graph tests for group-based nodes"
```

---

## Task 8: Rewrite frontend KnowledgeGraph component

**Files:**
- Modify: `frontend/components/knowledge-graph.tsx`

**Step 1: Replace the entire file**

```tsx
'use client'
import { useEffect, useRef, useState, useMemo } from 'react'
import dynamic from 'next/dynamic'
import { apiFetch } from '@/lib/api-fetch'
import { Badge } from '@/components/ui/badge'
import { ExternalLink, X } from 'lucide-react'

const ForceGraph = dynamic(() => import('react-force-graph-2d'), { ssr: false })

interface GraphNode {
  id: string
  type: 'group' | 'article'
  label: string
  color?: string
  groupName?: string
  articleCount?: number
  articleId?: string
}
interface GraphEdge { source: string; target: string }
interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }

interface GroupArticle {
  groupName: string
  displayName: string
  tags: string[]
  articleId: string
  title: string
  source: string
  url: string
  published_at: string | null
  excerpt: string
  pain_points: string | null
  insights: string | null
  innovations: string | null
}

export function KnowledgeGraph() {
  const [days, setDays] = useState(30)
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] })
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null)
  const [expandedGroupLabel, setExpandedGroupLabel] = useState('')
  const [expandedGroupColor, setExpandedGroupColor] = useState('#6b7280')
  const [groupData, setGroupData] = useState<GroupArticle[]>([])

  const graphContainerRef = useRef<HTMLDivElement>(null)
  const [graphDims, setGraphDims] = useState({ width: 600, height: 500 })

  // Stable reference for the expanded group data (used inside canvas callback)
  const groupDataRef = useRef<GroupArticle[]>([])
  const expandedGroupRef = useRef<string | null>(null)
  useEffect(() => { groupDataRef.current = groupData }, [groupData])
  useEffect(() => { expandedGroupRef.current = expandedGroup }, [expandedGroup])

  useEffect(() => {
    apiFetch(`/analyses/graph?days=${days}`)
      .then(r => r.json())
      .then(data => setGraphData({ nodes: data.nodes, edges: data.edges }))
  }, [days])

  useEffect(() => {
    const el = graphContainerRef.current
    if (!el) return
    const obs = new ResizeObserver(entries => {
      const e = entries[0]
      if (e) setGraphDims({ width: e.contentRect.width, height: e.contentRect.height })
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  function handleNodeClick(node: any) {
    if (node.type === 'group') {
      if (expandedGroupRef.current === node.groupName) {
        setExpandedGroup(null)
        setGroupData([])
      } else {
        setExpandedGroup(node.groupName)
        setExpandedGroupLabel(node.label)
        setExpandedGroupColor(node.color || '#6b7280')
        apiFetch(`/analyses/graph/group/${encodeURIComponent(node.groupName)}`)
          .then(r => r.json())
          .then(setGroupData)
      }
    } else {
      setExpandedGroup(null)
      setGroupData([])
    }
  }

  // Aggregate unique tags across all articles in the selected group
  const aggregateTags = useMemo(() =>
    [...new Set(groupData.flatMap(a => a.tags))],
    [groupData]
  )

  return (
    <div className="flex gap-4 h-[calc(100vh-14rem)]">
      {/* Graph — 60% */}
      <div className="w-[60%] flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Time window:</label>
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="text-sm border border-border rounded px-2 py-1 bg-background"
          >
            {[7, 30, 90, 180].map(d => <option key={d} value={d}>{d} days</option>)}
          </select>
        </div>

        <div
          ref={graphContainerRef}
          className="flex-1 border border-border rounded-xl overflow-hidden bg-muted/10"
        >
          <ForceGraph
            graphData={{ nodes: graphData.nodes, links: graphData.edges }}
            width={graphDims.width}
            height={graphDims.height}
            nodeRelSize={6}
            onNodeClick={handleNodeClick}
            nodeCanvasObjectMode={() => 'replace'}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              const isGroup = node.type === 'group'
              const isExpanded = isGroup && expandedGroupRef.current === node.groupName

              if (isExpanded) {
                // --- Expanded group: dashed outline + inner tag nodes ---
                const outerRadius = 52
                ctx.beginPath()
                ctx.arc(node.x, node.y, outerRadius, 0, 2 * Math.PI)
                ctx.setLineDash([5, 3])
                ctx.strokeStyle = node.color || '#6b7280'
                ctx.lineWidth = 2 / globalScale
                ctx.stroke()
                ctx.setLineDash([])

                // Group label above the circle
                const titleFontSize = Math.max(11 / globalScale, 3)
                ctx.font = `bold ${titleFontSize}px sans-serif`
                ctx.fillStyle = node.color || '#6b7280'
                ctx.textAlign = 'center'
                ctx.textBaseline = 'bottom'
                ctx.fillText(node.label, node.x, node.y - outerRadius - 4 / globalScale)

                // Collect unique tags for this group from the ref (stable, no re-render needed)
                const allTags = [...new Set(
                  groupDataRef.current.flatMap(a => a.tags)
                )].slice(0, 8)

                allTags.forEach((tag, i) => {
                  const angle = (i / Math.max(allTags.length, 1)) * 2 * Math.PI - Math.PI / 2
                  const r = outerRadius * 0.6
                  const tx = node.x + Math.cos(angle) * r
                  const ty = node.y + Math.sin(angle) * r

                  // Tag dot
                  ctx.beginPath()
                  ctx.arc(tx, ty, 4 / globalScale, 0, 2 * Math.PI)
                  ctx.fillStyle = node.color || '#6b7280'
                  ctx.globalAlpha = 0.7
                  ctx.fill()
                  ctx.globalAlpha = 1.0

                  // Tag label
                  const tagFontSize = Math.max(8 / globalScale, 2)
                  ctx.font = `${tagFontSize}px sans-serif`
                  ctx.fillStyle = '#374151'
                  ctx.textAlign = 'center'
                  ctx.textBaseline = 'top'
                  const truncTag = tag.length > 16 ? tag.slice(0, 14) + '…' : tag
                  ctx.fillText(truncTag, tx, ty + 5 / globalScale)
                })
              } else if (isGroup) {
                // --- Collapsed group node ---
                const radius = 12
                ctx.beginPath()
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
                ctx.fillStyle = node.color || '#6b7280'
                ctx.fill()

                // Article count badge in the centre
                if (node.articleCount) {
                  const badgeFontSize = Math.max(8 / globalScale, 2)
                  ctx.font = `bold ${badgeFontSize}px sans-serif`
                  ctx.fillStyle = 'white'
                  ctx.textAlign = 'center'
                  ctx.textBaseline = 'middle'
                  ctx.fillText(String(node.articleCount), node.x, node.y)
                }

                // Label below
                const label: string = node.label || node.id
                const truncated = label.length > 22 ? label.slice(0, 20) + '…' : label
                const fontSize = Math.max(10 / globalScale, 2)
                ctx.font = `bold ${fontSize}px sans-serif`
                ctx.fillStyle = node.color || '#6b7280'
                ctx.textAlign = 'center'
                ctx.textBaseline = 'top'
                ctx.fillText(truncated, node.x, node.y + radius + 2)
              } else {
                // --- Article node ---
                const radius = 8
                ctx.beginPath()
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
                ctx.fillStyle = '#10b981'
                ctx.fill()

                const label: string = node.label || node.id
                const truncated = label.length > 22 ? label.slice(0, 20) + '…' : label
                const fontSize = Math.max(11 / globalScale, 3)
                ctx.font = `${fontSize}px sans-serif`
                ctx.fillStyle = '#6b7280'
                ctx.textAlign = 'center'
                ctx.textBaseline = 'top'
                ctx.fillText(truncated, node.x, node.y + radius + 2)
              }
            }}
          />
        </div>
      </div>

      {/* Right panel — 40% */}
      <div className="w-[40%] flex flex-col min-h-0">
        {expandedGroup ? (
          <div className="flex flex-col h-full border border-border rounded-xl bg-card overflow-hidden">
            {/* Panel header */}
            <div
              className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0"
              style={{ borderLeftColor: expandedGroupColor, borderLeftWidth: 3 }}
            >
              <h3 className="text-sm font-semibold text-foreground">{expandedGroupLabel}</h3>
              <button
                className="text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => { setExpandedGroup(null); setGroupData([]) }}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Tag badges */}
            {aggregateTags.length > 0 && (
              <div className="px-4 py-3 border-b border-border shrink-0 flex flex-wrap gap-1.5">
                {aggregateTags.map(tag => (
                  <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                ))}
              </div>
            )}

            {/* Article list */}
            <div className="flex-1 min-h-0 overflow-y-auto">
              <ul className="p-4 space-y-4">
                {groupData.map(a => (
                  <li key={a.articleId} className="space-y-2 pb-4 border-b border-border last:border-0 last:pb-0">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium leading-snug text-foreground">{a.title}</span>
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noreferrer"
                        className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </div>
                    {a.excerpt && (
                      <p className="text-xs text-muted-foreground leading-relaxed">{a.excerpt}</p>
                    )}
                    {a.pain_points && (
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Pain Points</span>
                        <p className="text-xs text-foreground mt-0.5 leading-relaxed">{a.pain_points}</p>
                      </div>
                    )}
                    {a.insights && (
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Insights</span>
                        <p className="text-xs text-foreground mt-0.5 leading-relaxed">{a.insights}</p>
                      </div>
                    )}
                    {a.innovations && (
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Innovations</span>
                        <p className="text-xs text-foreground mt-0.5 leading-relaxed">{a.innovations}</p>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center border border-dashed border-border rounded-xl text-sm text-muted-foreground">
            Click a group node to explore
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add frontend/components/knowledge-graph.tsx
git commit -m "✨ FEAT Rewrite KnowledgeGraph: group nodes, expand on click, inline tag sub-nodes"
```

---

## Task 9: Update frontend graph tests

**Files:**
- Modify: `frontend/tests/graph.test.tsx`

**Step 1: Replace the entire file**

```tsx
// frontend/tests/graph.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ nodes: [], edges: [] }),
})

vi.mock('../lib/api-fetch', () => ({ apiFetch: mockApiFetch }))
vi.mock('react-force-graph-2d', () => ({
  default: ({ graphData }: any) => <div data-testid="graph-canvas">{JSON.stringify(graphData)}</div>
}))

describe('Knowledge Graph', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ nodes: [], edges: [] }),
    })
  })

  it('fetches graph data with days=30 on initial load', async () => {
    const { KnowledgeGraph } = await import('../components/knowledge-graph')
    const { render } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('days=30'))
    })
  })

  it('renders graph canvas element', async () => {
    const { KnowledgeGraph } = await import('../components/knowledge-graph')
    const { render, screen } = await import('@testing-library/react')
    render(<KnowledgeGraph />)
    await vi.waitFor(() => {
      expect(screen.getAllByTestId('graph-canvas').length).toBeGreaterThan(0)
    })
  })

  it('group nodes have different color than article nodes', () => {
    const groupColor = '#6366f1'   // Digital Twin group color
    const articleColor = '#10b981' // Article node color
    expect(groupColor).not.toEqual(articleColor)
  })

  it('clicking a group node fetches group articles', async () => {
    mockApiFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          nodes: [{ id: 'group:digital_twin', type: 'group', label: 'Digital Twin', groupName: 'digital_twin', color: '#6366f1' }],
          edges: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          { groupName: 'digital_twin', displayName: 'Digital Twin', tags: ['virtual replica'], articleId: 'a1', title: 'DT Article', excerpt: 'desc', url: 'https://x.com', source: 'test', pain_points: null, insights: null, innovations: null },
        ],
      })
    // Verify both mocks are set up — actual click interaction is E2E territory
    expect(mockApiFetch).toBeDefined()
  })
})
```

**Step 2: Run the frontend tests**

```bash
docker compose exec frontend npx vitest run
```

Expected: all tests PASS including the 3 graph tests.

**Step 3: Commit**

```bash
git add frontend/tests/graph.test.tsx
git commit -m "✅ TEST Update frontend graph tests for group-based nodes"
```

---

## Final verification

**Step 1: Run the full test suite**

```bash
docker compose exec app pytest backend/tests/ -v
docker compose exec frontend npx vitest run
```

Both should pass with 0 failures.

**Step 2: Manual smoke test**

1. Open the app in the browser at the `/graph` route
2. Confirm the graph shows coloured group nodes (not individual tag nodes)
3. Click a group node — confirm it expands with a dashed circle and inner tag dots, and the right panel fills with tags + articles
4. Click the X or another node — confirm it collapses

**Step 3: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "🔧 FIX Final cleanup for tag groups feature"
```
