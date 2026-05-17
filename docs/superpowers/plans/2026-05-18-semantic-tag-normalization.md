# Semantic Tag Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deduplicate LLM-generated tags using Gemini embeddings + cosine similarity, add a Tag management page, and wire failed-event persistence across the entire analysis pipeline.

**Architecture:** Tags produced by the LLM are embedded with `text-embedding-004` and compared against existing tags in the same group before being saved; high-similarity matches are auto-merged (≥0.92) or queued as pending suggestions (0.85–0.92). The event chain becomes `AnalysisCompleted → TagNormalizationHandler → TagNormalizationCompleted → TranslationHandler`, with a single `FailedTaskPersistenceHandler` collecting failures from every stage.

**Tech Stack:** Python 3.11, pgvector 0.3+, `google-genai` (existing), SQLAlchemy 2, Alembic, FastAPI, Next.js 16 / React 19, Tailwind CSS v4, Shadcn/UI.

**Spec:** `docs/superpowers/specs/2026-05-18-semantic-tag-normalization-design.md`

---

## File Map

**Create:**
- `alembic/versions/16_add_pgvector_and_tag_normalization.py`
- `alembic/versions/17_extend_failed_tasks.py`
- `models/tag_normalization_suggestion.py`
- `src/modules/intelligence/domain/value_objects/analysis_tag_group.py`
- `src/modules/intelligence/domain/entities/tag_normalization_suggestion.py`
- `src/modules/intelligence/domain/services/embedding_service.py`
- `src/modules/intelligence/domain/repositories/tag_repository.py`
- `src/infrastructure/intelligence/embedding/__init__.py`
- `src/infrastructure/intelligence/embedding/gemini_embedding_provider.py`
- `src/infrastructure/persistence/intelligence/tag_repo_impl.py`
- `src/modules/intelligence/application/use_cases/normalize_tags.py`
- `src/modules/intelligence/application/events/tag_normalization_completed.py`
- `src/modules/intelligence/application/events/tag_normalization_failed.py`
- `src/modules/intelligence/application/events/translation_failed.py`
- `src/shared/application/events/failed_event.py`
- `src/modules/intelligence/application/event_handlers/tag_normalization_handler.py`
- `src/modules/intelligence/application/event_handlers/failed_task_persistence_handler.py`
- `scripts/backfill_tag_embeddings.py`
- `backend/routers/tags.py`
- `frontend/app/tags/page.tsx`
- `frontend/lib/api/tags.ts`
- `frontend/components/features/tags/tag-group-card.tsx`
- `frontend/components/features/tags/pending-suggestions.tsx`
- `src/tests/unit/test_analysis_tag_group.py`
- `src/tests/unit/test_normalize_tags_use_case.py`
- `src/tests/unit/test_gemini_embedding_provider.py`
- `src/tests/unit/test_failed_task_persistence_handler.py`
- `src/tests/unit/test_tag_normalization_handler.py`

**Modify:**
- `docker-compose.yml` — postgres image → pgvector variant
- `pyproject.toml` — add `pgvector`
- `providers.toml` — add `[tag_normalization]` section
- `models/tag.py` — add `embedding` column
- `models/failed_task.py` — add `analysis_id`, `context`, `traceback` columns
- `models/__init__.py` — export `TagNormalizationSuggestion`
- `src/modules/intelligence/domain/value_objects/analysis_content.py` — use `AnalysisTagGroup`
- `src/modules/intelligence/domain/value_objects/__init__.py` — export `AnalysisTagGroup`
- `src/modules/intelligence/domain/repositories/__init__.py` — export `TagRepository`
- `src/modules/intelligence/domain/services/__init__.py` — export `EmbeddingService`
- `src/modules/intelligence/domain/entities/__init__.py` — export `TagNormalizationSuggestion`
- `src/modules/intelligence/application/events/__init__.py` — export new events
- `src/modules/intelligence/application/event_handlers/__init__.py` — export new handlers
- `src/modules/intelligence/application/use_cases/__init__.py` — export `NormalizeTagsUseCase`
- `src/modules/intelligence/application/events/analysis_completed.py` — add `tag_groups` field
- `src/modules/intelligence/application/events/analysis_failed.py` — add `task_type` field
- `src/infrastructure/intelligence/llm/providers/base_provider.py` — use `AnalysisTagGroup`
- `src/infrastructure/persistence/intelligence/analysis_repo_impl.py` — remove tag-save block
- `src/infrastructure/persistence/intelligence/__init__.py` — export `SqlAlchemyTagRepository`
- `src/infrastructure/persistence/shared/failed_task_repo_impl.py` — map new fields
- `src/modules/collection/domain/entities/failed_task.py` — add `analysis_id`, `context`, `traceback`
- `src/modules/intelligence/application/event_handlers/article_processed_handler.py` — pass `tag_groups` in event
- `src/modules/intelligence/application/event_handlers/analysis_completed_handler.py` — subscribe to `TagNormalizationCompletedEvent`; publish `TranslationFailedEvent`
- `src/bootstrap.py` — rewire all subscriptions
- `backend/main.py` — register tags router
- `frontend/components/features/navigation/nav-bar.tsx` — add Tags link
- `src/tests/unit/test_analysis_failed_handler.py` — update for renamed handler
- `src/tests/unit/test_llm_provider.py` — update for AnalysisTagGroup

---

## Task 1: Infrastructure Setup

**Files:**
- Modify: `docker-compose.yml`
- Modify: `pyproject.toml`
- Modify: `providers.toml`

- [ ] **Step 1: Change postgres image to pgvector variant**

In `docker-compose.yml`, find:
```yaml
  postgres:
    image: postgres:15
```
Change to:
```yaml
  postgres:
    image: pgvector/pgvector:pg15
```

- [ ] **Step 2: Add pgvector Python package**

In `pyproject.toml`, in the top-level `dependencies` list, add `"pgvector>=0.3"`:
```toml
dependencies = [
    "sqlalchemy>=2.0",
    "psycopg2-binary",
    "pgvector>=0.3",
    "structlog>=24.0",
    "alembic>=1.13",
    "geoip2>=4.8",
    "pydantic"
]
```

- [ ] **Step 3: Add tag_normalization config to providers.toml**

Append at the end of `providers.toml`:
```toml
[tag_normalization]
auto_merge_threshold = 0.92
suggest_threshold = 0.85
embedding_model = "text-embedding-004"
api_key_env = "GEMINI_API_KEY"
```

- [ ] **Step 4: Rebuild containers to pick up new image and package**

```bash
docker compose down && docker compose build --no-cache app backend test_service
```

Expected: builds succeed, no errors about missing `pgvector` package.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml pyproject.toml providers.toml
git commit -m "🔧 [FEAT] add pgvector image and dependency, add tag_normalization config"
```

---

## Task 2: Migration 16 — pgvector + tag_normalization_suggestions

**Files:**
- Create: `alembic/versions/16_add_pgvector_and_tag_normalization.py`

- [ ] **Step 1: Create migration file**

```python
# alembic/versions/16_add_pgvector_and_tag_normalization.py
"""add_pgvector_and_tag_normalization_suggestions

Revision ID: 16_add_pgvector_and_tag_normalization
Revises: 15_add_translations
Create Date: 2026-05-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "16_add_pgvector_and_tag_normalization"
down_revision: Union[str, Sequence[str], None] = "15_add_translations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Add embedding column to tags (nullable — backfilled separately)
    op.add_column(
        "tags",
        sa.Column("embedding", sa.Text(), nullable=True),  # stored as text, cast by pgvector
    )
    # Use raw DDL for vector type since SQLAlchemy doesn't know it natively
    op.execute("ALTER TABLE tags ALTER COLUMN embedding TYPE vector(768) USING embedding::vector")

    # 3. Create HNSW index for fast cosine similarity search
    op.execute(
        "CREATE INDEX idx_tags_embedding ON tags USING hnsw (embedding vector_cosine_ops)"
    )

    # 4. Create tag_normalization_suggestions table
    op.create_table(
        "tag_normalization_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("new_tag_id", UUID(as_uuid=True), nullable=False),
        sa.Column("existing_tag_id", UUID(as_uuid=True), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("article_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tns_new_tag", "tag_normalization_suggestions", "tags",
        ["new_tag_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_tns_existing_tag", "tag_normalization_suggestions", "tags",
        ["existing_tag_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_tns_article", "tag_normalization_suggestions", "articles",
        ["article_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_tns_status", "tag_normalization_suggestions", ["status"])
    op.create_index("idx_tns_new_tag_id", "tag_normalization_suggestions", ["new_tag_id"])


def downgrade() -> None:
    op.drop_index("idx_tns_new_tag_id", table_name="tag_normalization_suggestions")
    op.drop_index("idx_tns_status", table_name="tag_normalization_suggestions")
    op.drop_constraint("fk_tns_article", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_constraint("fk_tns_existing_tag", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_constraint("fk_tns_new_tag", "tag_normalization_suggestions", type_="foreignkey")
    op.drop_table("tag_normalization_suggestions")
    op.execute("DROP INDEX IF EXISTS idx_tags_embedding")
    op.drop_column("tags", "embedding")
```

- [ ] **Step 2: Run migration locally**

```bash
make migrate
```

Expected: `Running upgrade 15_add_translations -> 16_add_pgvector_and_tag_normalization, OK`

- [ ] **Step 3: Verify in psql**

```bash
docker compose exec postgres psql -U postgres -d postgres -c "\d tags" | grep embedding
docker compose exec postgres psql -U postgres -d postgres -c "\d tag_normalization_suggestions"
```

Expected: `embedding` column of type `vector(768)` in `tags`; full `tag_normalization_suggestions` table schema.

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/16_add_pgvector_and_tag_normalization.py
git commit -m "🗄️ [FEAT] migration 16: pgvector extension, embedding column, tag_normalization_suggestions table"
```

---

## Task 3: Migration 17 — Extend failed_tasks

**Files:**
- Create: `alembic/versions/17_extend_failed_tasks.py`

- [ ] **Step 1: Create migration file**

```python
# alembic/versions/17_extend_failed_tasks.py
"""extend_failed_tasks

Revision ID: 17_extend_failed_tasks
Revises: 16_add_pgvector_and_tag_normalization
Create Date: 2026-05-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "17_extend_failed_tasks"
down_revision: Union[str, Sequence[str], None] = "16_add_pgvector_and_tag_normalization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("failed_tasks", sa.Column(
        "analysis_id", UUID(as_uuid=True), nullable=True,
    ))
    op.create_foreign_key(
        "fk_failed_tasks_analysis_id", "failed_tasks", "analyses",
        ["analysis_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("failed_tasks", sa.Column("context", JSONB(), nullable=True))
    op.add_column("failed_tasks", sa.Column("traceback", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("failed_tasks", "traceback")
    op.drop_column("failed_tasks", "context")
    op.drop_constraint("fk_failed_tasks_analysis_id", "failed_tasks", type_="foreignkey")
    op.drop_column("failed_tasks", "analysis_id")
```

- [ ] **Step 2: Run migration**

```bash
make migrate
```

Expected: `Running upgrade 16_add_pgvector_and_tag_normalization -> 17_extend_failed_tasks, OK`

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/17_extend_failed_tasks.py
git commit -m "🗄️ [FEAT] migration 17: add analysis_id, context, traceback to failed_tasks"
```

---

## Task 4: ORM Model Updates

**Files:**
- Modify: `models/tag.py`
- Modify: `models/failed_task.py`
- Create: `models/tag_normalization_suggestion.py`
- Modify: `models/__init__.py`

- [ ] **Step 1: Add embedding column to Tag ORM model**

In `models/tag.py`, replace the import block and class:

```python
from sqlalchemy import Column, String, Text, Table, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, configure_mappers
from pgvector.sqlalchemy import Vector
import uuid

from models.base import Base
from models.tag_group import TagGroupDefinition  # noqa: F401 — registers mapper


article_tags = Table(
    'article_tags',
    Base.metadata,
    Column('article_id', UUID(as_uuid=True), ForeignKey('articles.id'), primary_key=True),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('tags.id'), primary_key=True),
)


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    tag_group_name = Column(String(100), nullable=False)
    embedding = Column(Vector(768), nullable=True)

    group_def = relationship(
        'TagGroupDefinition',
        primaryjoin='Tag.tag_group_name == TagGroupDefinition.name',
        foreign_keys='[Tag.tag_group_name]',
        uselist=False,
        viewonly=True,
    )
    articles = relationship('Article', secondary=article_tags, backref='tags')

    __table_args__ = (
        UniqueConstraint('name', 'tag_group_name', name='uq_tag_name_group'),
        Index('idx_tags_group', 'tag_group_name'),
    )


configure_mappers()
```

- [ ] **Step 2: Add new columns to FailedTask ORM model**

Replace `models/failed_task.py`:

```python
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid

from models.base import Base


class FailedTask(Base):
    __tablename__ = 'failed_tasks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(50), nullable=False)
    article_url = Column(Text)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id'))
    analysis_id = Column(UUID(as_uuid=True), ForeignKey('analyses.id', ondelete='SET NULL'), nullable=True)
    exception_type = Column(String(200))
    exception_message = Column(Text)
    context = Column(JSONB, nullable=True)
    traceback = Column(Text, nullable=True)
    failed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index('idx_failed_tasks_resolved', 'resolved'),
        Index('idx_failed_tasks_failed_at', 'failed_at'),
    )
```

- [ ] **Step 3: Create TagNormalizationSuggestion ORM model**

```python
# models/tag_normalization_suggestion.py
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from models.base import Base


class TagNormalizationSuggestion(Base):
    __tablename__ = 'tag_normalization_suggestions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    new_tag_id = Column(UUID(as_uuid=True), ForeignKey('tags.id', ondelete='CASCADE'), nullable=False)
    existing_tag_id = Column(UUID(as_uuid=True), ForeignKey('tags.id', ondelete='CASCADE'), nullable=False)
    similarity_score = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)

    new_tag = relationship('Tag', foreign_keys=[new_tag_id])
    existing_tag = relationship('Tag', foreign_keys=[existing_tag_id])

    __table_args__ = (
        Index('idx_tns_status', 'status'),
        Index('idx_tns_new_tag_id', 'new_tag_id'),
    )
```

- [ ] **Step 4: Export from models/__init__.py**

Read current `models/__init__.py`, then add the new import. Append:
```python
from .tag_normalization_suggestion import TagNormalizationSuggestion  # noqa: F401
```

- [ ] **Step 5: Verify models load correctly**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_orm_models.py -v
```

Expected: All existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add models/tag.py models/failed_task.py models/tag_normalization_suggestion.py models/__init__.py
git commit -m "🗄️ [FEAT] ORM models: add embedding to Tag, extend FailedTask, add TagNormalizationSuggestion"
```

---

## Task 5: AnalysisTagGroup VO + Fix LLM Parsing

**Files:**
- Create: `src/modules/intelligence/domain/value_objects/analysis_tag_group.py`
- Modify: `src/modules/intelligence/domain/value_objects/analysis_content.py`
- Modify: `src/modules/intelligence/domain/value_objects/__init__.py`
- Modify: `src/infrastructure/intelligence/llm/providers/base_provider.py`
- Create: `src/tests/unit/test_analysis_tag_group.py`

- [ ] **Step 1: Write failing test**

```python
# src/tests/unit/test_analysis_tag_group.py
def test_analysis_tag_group_holds_group_name_and_tags():
    from src.modules.intelligence.domain.value_objects.analysis_tag_group import AnalysisTagGroup
    tg = AnalysisTagGroup(group_name="digital_twin", tags=["virtual replica", "real-time sync"])
    assert tg.group_name == "digital_twin"
    assert tg.tags == ["virtual replica", "real-time sync"]


def test_analysis_content_tag_groups_uses_analysis_tag_group():
    from src.modules.intelligence.domain.value_objects.analysis_tag_group import AnalysisTagGroup
    from src.modules.intelligence.domain.value_objects.analysis_content import AnalysisContent
    tg = AnalysisTagGroup(group_name="g", tags=["t1"])
    content = AnalysisContent(tag_groups=[tg], pain_points=None, insights=None, innovations=None, summary=None)
    assert content.tag_groups[0].group_name == "g"
    assert content.tag_groups[0].tags == ["t1"]


def test_base_provider_parse_creates_analysis_tag_groups():
    from unittest.mock import MagicMock, patch
    from src.infrastructure.intelligence.llm.providers.base_provider import BaseProvider

    class ConcreteProvider(BaseProvider):
        def _call_api(self, content, prompt): return {}
        def _call_api_raw(self, content, prompt): return ""

    provider = ConcreteProvider(model="test")
    raw = {
        "tag_groups": [{"group": "digital_twin", "tags": ["virtual replica", "real-time sync"]}],
        "pain_points": "p", "insights": "i", "innovations": "n", "summary": "s",
        "_input_tokens": 10, "_output_tokens": 5,
    }
    content, _ = provider._parse_result(raw)
    from src.modules.intelligence.domain.value_objects.analysis_tag_group import AnalysisTagGroup
    assert isinstance(content.tag_groups[0], AnalysisTagGroup)
    assert content.tag_groups[0].group_name == "digital_twin"
    assert content.tag_groups[0].tags == ["virtual replica", "real-time sync"]
```

- [ ] **Step 2: Run test to verify failure**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_analysis_tag_group.py -v
```

Expected: `FAILED` — `AnalysisTagGroup` not found, `_parse_result` not found.

- [ ] **Step 3: Create AnalysisTagGroup VO**

```python
# src/modules/intelligence/domain/value_objects/analysis_tag_group.py
from typing import List, NamedTuple


class AnalysisTagGroup(NamedTuple):
    group_name: str
    tags: List[str]
```

- [ ] **Step 4: Update AnalysisContent to use AnalysisTagGroup**

Replace `src/modules/intelligence/domain/value_objects/analysis_content.py`:

```python
from dataclasses import dataclass
from typing import Optional, List
from .analysis_tag_group import AnalysisTagGroup


@dataclass
class AnalysisContent:
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    summary: Optional[str]
    tag_groups: Optional[List[AnalysisTagGroup]]
```

- [ ] **Step 5: Refactor base_provider.py — extract _parse_result and use AnalysisTagGroup**

In `src/infrastructure/intelligence/llm/providers/base_provider.py`:

Change the import at the top:
```python
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.modules.intelligence.domain.value_objects.analysis_tag_group import AnalysisTagGroup
```
(Remove `TagGroup` from this import — it's no longer needed here.)

Replace the `analyze()` method's parsing block (lines 113–132) and extract into a `_parse_result` method:

```python
    def _parse_result(self, result: dict) -> tuple[AnalysisContent, AnalysisMetadata]:
        tag_groups = [
            AnalysisTagGroup(
                group_name=tg.get("group", ""),
                tags=tg.get("tags", []),
            )
            for tg in result.get("tag_groups", [])
        ]
        analysis_content = AnalysisContent(
            pain_points=_to_str(result.get("pain_points")),
            insights=_to_str(result.get("insights")),
            innovations=_to_str(result.get("innovations")),
            summary=_to_str(result.get("summary")),
            tag_groups=tag_groups,
        )
        analysis_metadata = AnalysisMetadata(
            model_used=self._model,
            input_tokens=result.get("_input_tokens", 0),
            output_tokens=result.get("_output_tokens", 0),
        )
        return analysis_content, analysis_metadata

    def analyze(
        self,
        content: str,
        prompt: str,
    ) -> Optional[tuple[AnalysisContent, AnalysisMetadata]]:
        try:
            for attempt in self._retry:
                with attempt:
                    result = self._call_api(content, prompt)
        except RateLimitExhausted:
            raise
        except Exception as e:
            logger.warning("provider_analyze_failed", model=self._model, error=str(e))
            return None

        if not self._validate(result):
            logger.warning("provider_response_invalid", model=self._model, keys=list(result.keys()))
            return None

        return self._parse_result(result)
```

- [ ] **Step 6: Update __init__.py to export AnalysisTagGroup**

In `src/modules/intelligence/domain/value_objects/__init__.py`, add:
```python
from .analysis_tag_group import AnalysisTagGroup
```
And add `"AnalysisTagGroup"` to `__all__`.

- [ ] **Step 7: Run tests**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_analysis_tag_group.py src/tests/unit/test_llm_provider.py -v
```

Expected: all pass. If `test_llm_provider.py::test_analysis_content_has_all_fields` fails (it imports `TagGroup` from value_objects), update that test to use `AnalysisTagGroup`.

- [ ] **Step 8: Run full test suite to confirm no regressions**

```bash
make test
```

Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add src/modules/intelligence/domain/value_objects/analysis_tag_group.py \
        src/modules/intelligence/domain/value_objects/analysis_content.py \
        src/modules/intelligence/domain/value_objects/__init__.py \
        src/infrastructure/intelligence/llm/providers/base_provider.py \
        src/tests/unit/test_analysis_tag_group.py \
        src/tests/unit/test_llm_provider.py
git commit -m "♻️ [REFACTOR] introduce AnalysisTagGroup VO, fix TagGroup misuse in LLM parsing"
```

---

## Task 6: Domain Interfaces + Entities

**Files:**
- Create: `src/modules/intelligence/domain/services/embedding_service.py`
- Create: `src/modules/intelligence/domain/entities/tag_normalization_suggestion.py`
- Modify: `src/modules/collection/domain/entities/failed_task.py`
- Create: `src/modules/intelligence/domain/repositories/tag_repository.py`
- Modify: `src/modules/intelligence/domain/services/__init__.py`
- Modify: `src/modules/intelligence/domain/entities/__init__.py`
- Modify: `src/modules/intelligence/domain/repositories/__init__.py`

- [ ] **Step 1: Create EmbeddingService interface**

```python
# src/modules/intelligence/domain/services/embedding_service.py
from abc import ABC, abstractmethod
from typing import List


class EmbeddingService(ABC):

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return a 768-dimensional embedding vector for the given text."""
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Return embedding vectors for a list of texts (max 100 per call)."""
        ...
```

- [ ] **Step 2: Create TagNormalizationSuggestion domain entity**

```python
# src/modules/intelligence/domain/entities/tag_normalization_suggestion.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class TagNormalizationSuggestion:
    new_tag_id: UUID
    existing_tag_id: UUID
    similarity_score: float
    article_id: UUID
    status: str = "pending"           # pending | approved | rejected
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
```

- [ ] **Step 3: Extend FailedTask domain entity**

Replace `src/modules/collection/domain/entities/failed_task.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from uuid import UUID, uuid4


@dataclass
class FailedTask:
    task_type: str
    id: UUID = field(default_factory=uuid4)
    article_url: Optional[str] = None
    article_id: Optional[UUID] = None
    analysis_id: Optional[UUID] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
    failed_at: Optional[datetime] = None
    resolved: bool = False
```

- [ ] **Step 4: Create TagRepository interface**

```python
# src/modules/intelligence/domain/repositories/tag_repository.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple
from uuid import UUID

from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion


@dataclass
class TagData:
    id: Optional[UUID]
    name: str
    tag_group_name: str
    embedding: Optional[List[float]] = None


class TagRepository(ABC):

    @abstractmethod
    def find_by_group(self, group_name: str) -> List[TagData]:
        ...

    @abstractmethod
    def find_similar(
        self, embedding: List[float], group_name: str, threshold: float
    ) -> List[Tuple[TagData, float]]:
        """Return list of (tag, cosine_similarity) pairs above threshold, sorted by similarity desc."""
        ...

    @abstractmethod
    def save(self, name: str, tag_group_name: str, embedding: List[float]) -> TagData:
        """Upsert a tag and return it with its DB-assigned id."""
        ...

    @abstractmethod
    def link_to_article(self, tag_id: UUID, article_id: UUID) -> None:
        """Add entry to article_tags; silently ignore if already linked."""
        ...

    @abstractmethod
    def save_suggestion(self, suggestion: TagNormalizationSuggestion) -> TagNormalizationSuggestion:
        ...

    @abstractmethod
    def list_pending_suggestions(self) -> List[TagNormalizationSuggestion]:
        ...

    @abstractmethod
    def approve_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        """Re-point all article_tags from new_tag to existing_tag, delete new_tag, mark approved."""
        ...

    @abstractmethod
    def reject_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        ...
```

Note: add `from dataclasses import dataclass` at the top of `tag_repository.py`.

- [ ] **Step 5: Update __init__.py exports**

`src/modules/intelligence/domain/services/__init__.py` — add:
```python
from .embedding_service import EmbeddingService
```
and add `"EmbeddingService"` to `__all__`.

`src/modules/intelligence/domain/entities/__init__.py` — add:
```python
from .tag_normalization_suggestion import TagNormalizationSuggestion
```
and add `"TagNormalizationSuggestion"` to `__all__`.

`src/modules/intelligence/domain/repositories/__init__.py` — add:
```python
from .tag_repository import TagRepository, TagData
```
and add `"TagRepository"`, `"TagData"` to `__all__`.

- [ ] **Step 6: Update failed_task_repo_impl to map new fields**

In `src/infrastructure/persistence/shared/failed_task_repo_impl.py`, update `save()`:

```python
    def save(self, task: FailedTask) -> None:
        from models.failed_task import FailedTask as FailedTaskModel

        row = FailedTaskModel(
            id=task.id,
            task_type=task.task_type,
            article_url=task.article_url,
            article_id=task.article_id,
            analysis_id=task.analysis_id,
            exception_type=task.exception_type,
            exception_message=task.exception_message,
            context=task.context,
            traceback=task.traceback,
            failed_at=task.failed_at,
        )
        self._session.add(row)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("failed_task_saved", task_type=task.task_type,
                    article_id=str(task.article_id) if task.article_id else None)
```

- [ ] **Step 7: Run tests**

```bash
make test
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/modules/intelligence/domain/services/embedding_service.py \
        src/modules/intelligence/domain/entities/tag_normalization_suggestion.py \
        src/modules/collection/domain/entities/failed_task.py \
        src/modules/intelligence/domain/repositories/tag_repository.py \
        src/modules/intelligence/domain/services/__init__.py \
        src/modules/intelligence/domain/entities/__init__.py \
        src/modules/intelligence/domain/repositories/__init__.py \
        src/infrastructure/persistence/shared/failed_task_repo_impl.py
git commit -m "🏗️ [FEAT] domain interfaces: EmbeddingService, TagRepository, TagData, TagNormalizationSuggestion; extend FailedTask"
```

---

## Task 7: GeminiEmbeddingProvider

**Files:**
- Create: `src/infrastructure/intelligence/embedding/__init__.py`
- Create: `src/infrastructure/intelligence/embedding/gemini_embedding_provider.py`
- Create: `src/tests/unit/test_gemini_embedding_provider.py`

- [ ] **Step 1: Write failing tests**

```python
# src/tests/unit/test_gemini_embedding_provider.py
import pytest
from unittest.mock import MagicMock, patch


def _make_mock_embed_response(vectors):
    response = MagicMock()
    response.embeddings = [MagicMock(values=v) for v in vectors]
    return response


def test_embed_returns_768_dim_vector():
    from src.infrastructure.intelligence.embedding.gemini_embedding_provider import GeminiEmbeddingProvider
    provider = GeminiEmbeddingProvider(api_key="test-key", model="text-embedding-004")
    provider._client = MagicMock()
    provider._client.models.embed_content.return_value = _make_mock_embed_response([[0.1] * 768])

    result = provider.embed("hello world")

    assert len(result) == 768
    assert result[0] == 0.1
    provider._client.models.embed_content.assert_called_once_with(
        model="text-embedding-004",
        contents=["hello world"],
        config={"task_type": "CLASSIFICATION"},
    )


def test_embed_batch_returns_one_vector_per_text():
    from src.infrastructure.intelligence.embedding.gemini_embedding_provider import GeminiEmbeddingProvider
    provider = GeminiEmbeddingProvider(api_key="test-key", model="text-embedding-004")
    provider._client = MagicMock()
    provider._client.models.embed_content.return_value = _make_mock_embed_response(
        [[0.1] * 768, [0.2] * 768]
    )

    results = provider.embed_batch(["text one", "text two"])

    assert len(results) == 2
    assert len(results[0]) == 768
    assert len(results[1]) == 768


def test_embed_batch_splits_at_100():
    from src.infrastructure.intelligence.embedding.gemini_embedding_provider import GeminiEmbeddingProvider
    provider = GeminiEmbeddingProvider(api_key="test-key", model="text-embedding-004")
    provider._client = MagicMock()
    provider._client.models.embed_content.return_value = _make_mock_embed_response(
        [[0.1] * 768] * 100
    )

    texts = [f"text {i}" for i in range(150)]
    provider.embed_batch(texts)

    assert provider._client.models.embed_content.call_count == 2
```

- [ ] **Step 2: Run tests to verify failure**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_gemini_embedding_provider.py -v
```

Expected: `FAILED` — module not found.

- [ ] **Step 3: Create embedding package**

```python
# src/infrastructure/intelligence/embedding/__init__.py
from .gemini_embedding_provider import GeminiEmbeddingProvider

__all__ = ["GeminiEmbeddingProvider"]
```

- [ ] **Step 4: Implement GeminiEmbeddingProvider**

```python
# src/infrastructure/intelligence/embedding/gemini_embedding_provider.py
from typing import List

from google import genai

from src.modules.intelligence.domain.services.embedding_service import EmbeddingService
from src.shared.logging import get_logger

logger = get_logger(__name__)

_BATCH_SIZE = 100


class GeminiEmbeddingProvider(EmbeddingService):

    def __init__(self, api_key: str, model: str = "text-embedding-004") -> None:
        self._model = model
        self._client = genai.Client(api_key=api_key)

    def embed(self, text: str) -> List[float]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=[text],
            config={"task_type": "CLASSIFICATION"},
        )
        logger.debug("embedding_created", model=self._model)
        return list(response.embeddings[0].values)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            response = self._client.models.embed_content(
                model=self._model,
                contents=batch,
                config={"task_type": "CLASSIFICATION"},
            )
            results.extend(list(e.values) for e in response.embeddings)
            logger.debug("embedding_batch_created", model=self._model, count=len(batch))
        return results
```

- [ ] **Step 5: Run tests**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_gemini_embedding_provider.py -v
```

Expected: all 3 pass.

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/intelligence/embedding/ src/tests/unit/test_gemini_embedding_provider.py
git commit -m "🤖 [FEAT] GeminiEmbeddingProvider: embed + embed_batch with batch-size guard"
```

---

## Task 8: SqlAlchemyTagRepository

**Files:**
- Create: `src/infrastructure/persistence/intelligence/tag_repo_impl.py`
- Modify: `src/infrastructure/persistence/intelligence/__init__.py`

- [ ] **Step 1: Implement SqlAlchemyTagRepository**

```python
# src/infrastructure/persistence/intelligence/tag_repo_impl.py
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text

from src.modules.intelligence.domain.repositories.tag_repository import TagRepository, TagData
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTagRepository(TagRepository):

    def __init__(self, session) -> None:
        self._session = session

    def find_by_group(self, group_name: str) -> List[TagData]:
        from models.tag import Tag
        rows = self._session.query(Tag).filter_by(tag_group_name=group_name).all()
        return [
            TagData(id=r.id, name=r.name, tag_group_name=r.tag_group_name,
                    embedding=list(r.embedding) if r.embedding is not None else None)
            for r in rows
        ]

    def find_similar(
        self, embedding: List[float], group_name: str, threshold: float
    ) -> List[Tuple[TagData, float]]:
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
        rows = self._session.execute(text("""
            SELECT id, name, tag_group_name,
                   1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM tags
            WHERE tag_group_name = :group_name
              AND embedding IS NOT NULL
              AND (1 - (embedding <=> CAST(:vec AS vector))) >= :threshold
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT 5
        """), {"vec": vec_str, "group_name": group_name, "threshold": threshold}).fetchall()

        return [
            (TagData(id=row[0], name=row[1], tag_group_name=row[2]), float(row[3]))
            for row in rows
        ]

    def save(self, name: str, tag_group_name: str, embedding: List[float]) -> TagData:
        from models.tag import Tag
        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"

        tag = self._session.query(Tag).filter_by(
            name=name, tag_group_name=tag_group_name
        ).first()
        if not tag:
            tag = Tag(name=name, tag_group_name=tag_group_name)
            self._session.add(tag)
            self._session.flush()

        # Update embedding using raw SQL to avoid SQLAlchemy vector serialization issues
        self._session.execute(text(
            "UPDATE tags SET embedding = CAST(:vec AS vector) WHERE id = :id"
        ), {"vec": vec_str, "id": str(tag.id)})

        return TagData(id=tag.id, name=tag.name, tag_group_name=tag.tag_group_name,
                       embedding=embedding)

    def link_to_article(self, tag_id: UUID, article_id: UUID) -> None:
        from models.article import Article
        from models.tag import Tag
        article = self._session.query(Article).filter_by(id=article_id).first()
        tag = self._session.query(Tag).filter_by(id=tag_id).first()
        if article and tag and tag not in article.tags:
            article.tags.append(tag)

    def save_suggestion(self, suggestion: TagNormalizationSuggestion) -> TagNormalizationSuggestion:
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        row = SuggestionModel(
            new_tag_id=suggestion.new_tag_id,
            existing_tag_id=suggestion.existing_tag_id,
            similarity_score=suggestion.similarity_score,
            status=suggestion.status,
            article_id=suggestion.article_id,
            created_at=suggestion.created_at or datetime.now(timezone.utc),
        )
        self._session.add(row)
        self._session.flush()
        suggestion.id = row.id
        return suggestion

    def list_pending_suggestions(self) -> List[TagNormalizationSuggestion]:
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        rows = self._session.query(SuggestionModel).filter_by(status="pending").all()
        return [
            TagNormalizationSuggestion(
                id=r.id,
                new_tag_id=r.new_tag_id,
                existing_tag_id=r.existing_tag_id,
                similarity_score=r.similarity_score,
                article_id=r.article_id,
                status=r.status,
            )
            for r in rows
        ]

    def approve_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        suggestion = self._session.query(SuggestionModel).filter_by(id=suggestion_id).first()
        if not suggestion:
            return

        # Re-point all article_tags rows from new_tag to existing_tag
        self._session.execute(text("""
            INSERT INTO article_tags (article_id, tag_id)
            SELECT article_id, :existing_id FROM article_tags WHERE tag_id = :new_id
            ON CONFLICT DO NOTHING
        """), {"existing_id": str(suggestion.existing_tag_id), "new_id": str(suggestion.new_tag_id)})

        # Remove old article_tags rows pointing to new_tag
        self._session.execute(text(
            "DELETE FROM article_tags WHERE tag_id = :new_id"
        ), {"new_id": str(suggestion.new_tag_id)})

        # Delete the new (duplicate) tag
        self._session.execute(text(
            "DELETE FROM tags WHERE id = :new_id"
        ), {"new_id": str(suggestion.new_tag_id)})

        # Mark resolved
        suggestion.status = "approved"
        suggestion.resolved_at = datetime.now(timezone.utc)
        suggestion.resolved_by = resolved_by

        logger.info("tag_suggestion_approved", suggestion_id=str(suggestion_id))

    def reject_suggestion(self, suggestion_id: UUID, resolved_by: UUID) -> None:
        from models.tag_normalization_suggestion import TagNormalizationSuggestion as SuggestionModel
        suggestion = self._session.query(SuggestionModel).filter_by(id=suggestion_id).first()
        if not suggestion:
            return
        suggestion.status = "rejected"
        suggestion.resolved_at = datetime.now(timezone.utc)
        suggestion.resolved_by = resolved_by
        logger.info("tag_suggestion_rejected", suggestion_id=str(suggestion_id))

    def commit(self) -> None:
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
```

- [ ] **Step 2: Export from infrastructure __init__.py**

In `src/infrastructure/persistence/intelligence/__init__.py`, add:
```python
from .tag_repo_impl import SqlAlchemyTagRepository
```
and add `"SqlAlchemyTagRepository"` to `__all__`.

- [ ] **Step 3: Run existing tests to confirm no regressions**

```bash
make test
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/infrastructure/persistence/intelligence/tag_repo_impl.py \
        src/infrastructure/persistence/intelligence/__init__.py
git commit -m "🗄️ [FEAT] SqlAlchemyTagRepository: find_similar with pgvector, save, link_to_article, suggestion CRUD"
```

---

## Task 9: NormalizeTagsUseCase

**Files:**
- Create: `src/modules/intelligence/application/use_cases/normalize_tags.py`
- Modify: `src/modules/intelligence/application/use_cases/__init__.py`
- Create: `src/tests/unit/test_normalize_tags_use_case.py`

- [ ] **Step 1: Write failing tests**

```python
# src/tests/unit/test_normalize_tags_use_case.py
import uuid
from unittest.mock import MagicMock, call

import pytest

from src.modules.intelligence.domain.repositories.tag_repository import TagData
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion


def _make_use_case(auto_merge=0.92, suggest=0.85):
    from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsUseCase
    embedding_svc = MagicMock()
    tag_repo = MagicMock()
    tag_repo.commit = MagicMock()
    return NormalizeTagsUseCase(
        embedding_service=embedding_svc,
        tag_repository=tag_repo,
        auto_merge_threshold=auto_merge,
        suggest_threshold=suggest,
    ), embedding_svc, tag_repo


def test_high_similarity_reuses_existing_tag_without_saving_new():
    uc, embed_svc, tag_repo = _make_use_case()
    analysis_id = uuid.uuid4()
    article_id = uuid.uuid4()
    existing_tag = TagData(id=uuid.uuid4(), name="real-time sync", tag_group_name="digital_twin")

    embed_svc.embed.return_value = [0.1] * 768
    tag_repo.find_similar.return_value = [(existing_tag, 0.95)]  # above auto_merge

    uc.execute(analysis_id=analysis_id, article_id=article_id,
               tag_groups=[("digital_twin", ["real time sync"])])

    tag_repo.save.assert_not_called()
    tag_repo.link_to_article.assert_called_once_with(existing_tag.id, article_id)
    tag_repo.save_suggestion.assert_not_called()


def test_mid_similarity_saves_new_tag_and_creates_suggestion():
    uc, embed_svc, tag_repo = _make_use_case()
    analysis_id = uuid.uuid4()
    article_id = uuid.uuid4()
    existing_tag = TagData(id=uuid.uuid4(), name="real-time sync", tag_group_name="digital_twin")
    new_tag = TagData(id=uuid.uuid4(), name="real time sync", tag_group_name="digital_twin")

    embed_svc.embed.return_value = [0.1] * 768
    tag_repo.find_similar.return_value = [(existing_tag, 0.88)]  # mid range
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=analysis_id, article_id=article_id,
               tag_groups=[("digital_twin", ["real time sync"])])

    tag_repo.save.assert_called_once_with("real time sync", "digital_twin", [0.1] * 768)
    tag_repo.link_to_article.assert_called_once_with(new_tag.id, article_id)
    tag_repo.save_suggestion.assert_called_once()
    suggestion: TagNormalizationSuggestion = tag_repo.save_suggestion.call_args[0][0]
    assert suggestion.new_tag_id == new_tag.id
    assert suggestion.existing_tag_id == existing_tag.id
    assert suggestion.similarity_score == pytest.approx(0.88)


def test_low_similarity_saves_new_tag_without_suggestion():
    uc, embed_svc, tag_repo = _make_use_case()
    new_tag = TagData(id=uuid.uuid4(), name="brand new concept", tag_group_name="digital_twin")

    embed_svc.embed.return_value = [0.1] * 768
    tag_repo.find_similar.return_value = []  # no similar tags
    tag_repo.save.return_value = new_tag

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("digital_twin", ["brand new concept"])])

    tag_repo.save.assert_called_once()
    tag_repo.link_to_article.assert_called_once()
    tag_repo.save_suggestion.assert_not_called()


def test_empty_tag_name_is_skipped():
    uc, embed_svc, tag_repo = _make_use_case()
    tag_repo.find_similar.return_value = []
    tag_repo.save.return_value = TagData(id=uuid.uuid4(), name="x", tag_group_name="g")

    uc.execute(analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
               tag_groups=[("g", ["", "   "])])

    embed_svc.embed.assert_not_called()
    tag_repo.save.assert_not_called()


def test_execute_returns_success_result():
    from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsResult
    uc, embed_svc, tag_repo = _make_use_case()
    a_id = uuid.uuid4()
    tag_repo.find_similar.return_value = []
    tag_repo.save.return_value = TagData(id=uuid.uuid4(), name="t", tag_group_name="g")

    result = uc.execute(analysis_id=a_id, article_id=uuid.uuid4(),
                        tag_groups=[("g", ["t"])])

    assert result.success is True
    assert result.analysis_id == a_id
```

- [ ] **Step 2: Run tests to verify failure**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_normalize_tags_use_case.py -v
```

Expected: `FAILED` — module not found.

- [ ] **Step 3: Implement NormalizeTagsUseCase**

```python
# src/modules/intelligence/application/use_cases/normalize_tags.py
import traceback as tb
from dataclasses import dataclass
from typing import List, Optional, Tuple
from uuid import UUID

from src.modules.intelligence.domain.services.embedding_service import EmbeddingService
from src.modules.intelligence.domain.repositories.tag_repository import TagRepository
from src.modules.intelligence.domain.entities.tag_normalization_suggestion import TagNormalizationSuggestion
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class NormalizeTagsResult:
    success: bool
    analysis_id: UUID
    article_id: UUID
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    traceback: Optional[str] = None


class NormalizeTagsUseCase:

    def __init__(
        self,
        embedding_service: EmbeddingService,
        tag_repository: TagRepository,
        auto_merge_threshold: float = 0.92,
        suggest_threshold: float = 0.85,
    ) -> None:
        self._embedding_service = embedding_service
        self._tag_repository = tag_repository
        self._auto_merge_threshold = auto_merge_threshold
        self._suggest_threshold = suggest_threshold

    def execute(
        self,
        analysis_id: UUID,
        article_id: UUID,
        tag_groups: List[Tuple[str, List[str]]],
    ) -> NormalizeTagsResult:
        try:
            self._process(analysis_id, article_id, tag_groups)
            self._tag_repository.commit()
            return NormalizeTagsResult(success=True, analysis_id=analysis_id, article_id=article_id)
        except Exception as e:
            logger.error("normalize_tags_failed", analysis_id=str(analysis_id), error=str(e))
            return NormalizeTagsResult(
                success=False,
                analysis_id=analysis_id,
                article_id=article_id,
                exception_type=type(e).__name__,
                exception_message=str(e),
                traceback=tb.format_exc(),
            )

    def _process(
        self,
        analysis_id: UUID,
        article_id: UUID,
        tag_groups: List[Tuple[str, List[str]]],
    ) -> None:
        for group_name, tag_names in tag_groups:
            for tag_name in tag_names:
                if not tag_name or not tag_name.strip():
                    continue
                self._process_tag(tag_name.strip(), group_name, article_id)

    def _process_tag(self, tag_name: str, group_name: str, article_id: UUID) -> None:
        embedding = self._embedding_service.embed(tag_name)
        similar = self._tag_repository.find_similar(embedding, group_name, self._suggest_threshold)

        if similar:
            best_tag, best_score = similar[0]

            if best_score >= self._auto_merge_threshold:
                # Auto-merge: reuse existing tag
                self._tag_repository.link_to_article(best_tag.id, article_id)
                logger.info("tag_auto_merged", tag=tag_name, merged_into=best_tag.name,
                            similarity=best_score)
                return

            # Mid-range: save new tag and create pending suggestion
            new_tag = self._tag_repository.save(tag_name, group_name, embedding)
            self._tag_repository.link_to_article(new_tag.id, article_id)
            suggestion = TagNormalizationSuggestion(
                new_tag_id=new_tag.id,
                existing_tag_id=best_tag.id,
                similarity_score=best_score,
                article_id=article_id,
            )
            self._tag_repository.save_suggestion(suggestion)
            logger.info("tag_suggestion_created", tag=tag_name, similar_to=best_tag.name,
                        similarity=best_score)
            return

        # No similar tag found: save as new
        new_tag = self._tag_repository.save(tag_name, group_name, embedding)
        self._tag_repository.link_to_article(new_tag.id, article_id)
        logger.info("tag_created", tag=tag_name, group=group_name)
```

- [ ] **Step 4: Update use_cases __init__.py**

In `src/modules/intelligence/application/use_cases/__init__.py`, add:
```python
from .normalize_tags import NormalizeTagsUseCase, NormalizeTagsResult
```
and add both to `__all__`.

- [ ] **Step 5: Run tests**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_normalize_tags_use_case.py -v
```

Expected: all 5 pass.

- [ ] **Step 6: Commit**

```bash
git add src/modules/intelligence/application/use_cases/normalize_tags.py \
        src/modules/intelligence/application/use_cases/__init__.py \
        src/tests/unit/test_normalize_tags_use_case.py
git commit -m "✨ [FEAT] NormalizeTagsUseCase: embed + cosine similarity deduplication with auto-merge and suggestion"
```

---

## Task 10: Events Refactor + FailedTaskPersistenceHandler

**Files:**
- Modify: `src/modules/intelligence/application/events/analysis_completed.py`
- Modify: `src/modules/intelligence/application/events/analysis_failed.py`
- Create: `src/modules/intelligence/application/events/tag_normalization_completed.py`
- Create: `src/modules/intelligence/application/events/tag_normalization_failed.py`
- Create: `src/modules/intelligence/application/events/translation_failed.py`
- Create: `src/shared/application/events/failed_event.py`
- Create: `src/modules/intelligence/application/event_handlers/failed_task_persistence_handler.py`
- Modify: `src/modules/intelligence/application/events/__init__.py`
- Modify: `src/modules/intelligence/application/event_handlers/__init__.py`
- Create: `src/tests/unit/test_failed_task_persistence_handler.py`

- [ ] **Step 1: Extend AnalysisCompletedEvent with tag_groups**

Replace `src/modules/intelligence/application/events/analysis_completed.py`:

```python
from dataclasses import dataclass, field
from typing import List, Tuple
from uuid import UUID


@dataclass(frozen=True)
class AnalysisCompletedEvent:
    """Published by ArticleProcessedHandler after successful analysis save."""
    analysis_id: UUID
    article_id: UUID
    tag_groups: tuple = field(default_factory=tuple)
    # tuple of (group_name: str, tags: list[str]) — passed through to TagNormalizationHandler
```

- [ ] **Step 2: Add task_type to AnalysisFailedEvent for protocol compatibility**

Replace `src/modules/intelligence/application/events/analysis_failed.py`:

```python
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class AnalysisFailedEvent:
    """Published by ArticleProcessedHandler when LLM analysis or persistence fails."""
    article_id: UUID
    article_url: str
    task_type: str = "analyze"
    analysis_id: Optional[UUID] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
```

- [ ] **Step 3: Create TagNormalizationCompletedEvent**

```python
# src/modules/intelligence/application/events/tag_normalization_completed.py
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TagNormalizationCompletedEvent:
    """Published by TagNormalizationHandler after successful tag normalization."""
    analysis_id: UUID
    article_id: UUID
```

- [ ] **Step 4: Create TagNormalizationFailedEvent**

```python
# src/modules/intelligence/application/events/tag_normalization_failed.py
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class TagNormalizationFailedEvent:
    analysis_id: UUID
    article_id: UUID
    task_type: str = "tag_normalization"
    article_url: Optional[str] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
```

- [ ] **Step 5: Create TranslationFailedEvent**

```python
# src/modules/intelligence/application/events/translation_failed.py
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class TranslationFailedEvent:
    analysis_id: UUID
    article_id: UUID
    task_type: str = "translate_article"
    article_url: Optional[str] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
```

- [ ] **Step 6: Create FailedEvent protocol**

```python
# src/shared/application/events/failed_event.py
from typing import Optional, runtime_checkable, Protocol
from uuid import UUID


@runtime_checkable
class FailedEvent(Protocol):
    task_type: str
    article_id: Optional[UUID]
    analysis_id: Optional[UUID]
    article_url: Optional[str]
    exception_type: Optional[str]
    exception_message: Optional[str]
    context: Optional[dict]
    traceback: Optional[str]
```

- [ ] **Step 7: Write failing test for FailedTaskPersistenceHandler**

```python
# src/tests/unit/test_failed_task_persistence_handler.py
import uuid
from unittest.mock import MagicMock

from src.modules.intelligence.application.events.analysis_failed import AnalysisFailedEvent
from src.modules.intelligence.application.events.tag_normalization_failed import TagNormalizationFailedEvent
from src.modules.intelligence.application.events.translation_failed import TranslationFailedEvent
from src.modules.collection.domain.entities import FailedTask


def _make_repo():
    return MagicMock()


def test_handles_analysis_failed_event():
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo)
    event = AnalysisFailedEvent(
        article_id=uuid.uuid4(), article_url="https://x.com", exception_type="LLMError",
        exception_message="failed",
    )
    handler.handle(event)

    repo.save.assert_called_once()
    task: FailedTask = repo.save.call_args[0][0]
    assert task.task_type == "analyze"
    assert task.article_url == "https://x.com"
    assert task.exception_type == "LLMError"
    assert task.resolved is False


def test_handles_tag_normalization_failed_event():
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo)
    analysis_id = uuid.uuid4()
    event = TagNormalizationFailedEvent(
        analysis_id=analysis_id, article_id=uuid.uuid4(),
        exception_type="EmbeddingError", exception_message="quota exceeded",
        context={"group": "digital_twin"},
    )
    handler.handle(event)

    repo.save.assert_called_once()
    task: FailedTask = repo.save.call_args[0][0]
    assert task.task_type == "tag_normalization"
    assert task.analysis_id == analysis_id
    assert task.context == {"group": "digital_twin"}


def test_handles_translation_failed_event():
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo)
    event = TranslationFailedEvent(
        analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
        task_type="translate_article", context={"language": "zh-TW"},
    )
    handler.handle(event)

    task: FailedTask = repo.save.call_args[0][0]
    assert task.task_type == "translate_article"
    assert task.context == {"language": "zh-TW"}


def test_does_not_raise_when_repo_fails():
    from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import (
        FailedTaskPersistenceHandler,
    )
    repo = _make_repo()
    repo.save.side_effect = Exception("DB down")
    handler = FailedTaskPersistenceHandler(failed_task_repository=repo)
    # Should not propagate the exception
    handler.handle(AnalysisFailedEvent(article_id=uuid.uuid4(), article_url="https://x.com"))
```

- [ ] **Step 8: Implement FailedTaskPersistenceHandler**

```python
# src/modules/intelligence/application/event_handlers/failed_task_persistence_handler.py
from datetime import datetime, timezone

from src.modules.collection.domain.entities import FailedTask
from src.shared.domain.repositories import FailedTaskRepository
from src.shared.application.events.failed_event import FailedEvent
from src.shared.logging import get_logger

logger = get_logger(__name__)


class FailedTaskPersistenceHandler:

    def __init__(self, failed_task_repository: FailedTaskRepository) -> None:
        self._repo = failed_task_repository

    def handle(self, event: FailedEvent) -> None:
        task = FailedTask(
            task_type=getattr(event, "task_type", "unknown"),
            article_id=getattr(event, "article_id", None),
            article_url=getattr(event, "article_url", None),
            analysis_id=getattr(event, "analysis_id", None),
            exception_type=getattr(event, "exception_type", None),
            exception_message=getattr(event, "exception_message", None),
            context=getattr(event, "context", None),
            traceback=getattr(event, "traceback", None),
            failed_at=datetime.now(timezone.utc),
        )
        try:
            self._repo.save(task)
            logger.info(
                "failed_task_persisted",
                task_type=task.task_type,
                article_id=str(task.article_id) if task.article_id else None,
            )
        except Exception as e:
            logger.error("failed_task_save_error", task_type=task.task_type, error=str(e))
```

- [ ] **Step 9: Update events __init__.py**

Replace `src/modules/intelligence/application/events/__init__.py`:

```python
from .analysis_failed import AnalysisFailedEvent
from .analysis_completed import AnalysisCompletedEvent
from .tag_normalization_completed import TagNormalizationCompletedEvent
from .tag_normalization_failed import TagNormalizationFailedEvent
from .translation_failed import TranslationFailedEvent

__all__ = [
    'AnalysisFailedEvent',
    'AnalysisCompletedEvent',
    'TagNormalizationCompletedEvent',
    'TagNormalizationFailedEvent',
    'TranslationFailedEvent',
]
```

- [ ] **Step 10: Update event_handlers __init__.py**

In `src/modules/intelligence/application/event_handlers/__init__.py`, add:
```python
from .failed_task_persistence_handler import FailedTaskPersistenceHandler
```
and add `"FailedTaskPersistenceHandler"` to `__all__`. Keep `AnalysisFailedHandler` export for now (will be removed in Task 11).

- [ ] **Step 11: Run all tests**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_failed_task_persistence_handler.py src/tests/unit/test_analysis_failed_handler.py -v
```

Expected: all pass. `test_analysis_failed_handler.py` still imports `AnalysisFailedHandler` — update that file to import `FailedTaskPersistenceHandler` instead and adjust assertions for `task_type="analyze"`.

- [ ] **Step 12: Run full test suite**

```bash
make test
```

Expected: all green.

- [ ] **Step 13: Commit**

```bash
git add src/modules/intelligence/application/events/ \
        src/shared/application/events/failed_event.py \
        src/modules/intelligence/application/event_handlers/failed_task_persistence_handler.py \
        src/modules/intelligence/application/event_handlers/__init__.py \
        src/tests/unit/test_failed_task_persistence_handler.py \
        src/tests/unit/test_analysis_failed_handler.py
git commit -m "🔄 [FEAT] events refactor: new failed/completed events, FailedTaskPersistenceHandler replaces AnalysisFailedHandler"
```

---

## Task 11: TagNormalizationHandler + Pipeline Rewiring

**Files:**
- Create: `src/modules/intelligence/application/event_handlers/tag_normalization_handler.py`
- Modify: `src/modules/intelligence/application/event_handlers/article_processed_handler.py`
- Modify: `src/modules/intelligence/application/event_handlers/analysis_completed_handler.py`
- Modify: `src/infrastructure/persistence/intelligence/analysis_repo_impl.py`
- Modify: `src/bootstrap.py`
- Create: `src/tests/unit/test_tag_normalization_handler.py`

- [ ] **Step 1: Write failing test for TagNormalizationHandler**

```python
# src/tests/unit/test_tag_normalization_handler.py
import uuid
from unittest.mock import MagicMock

from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    TagNormalizationCompletedEvent,
    TagNormalizationFailedEvent,
)
from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsResult


def _make_handler():
    from src.modules.intelligence.application.event_handlers.tag_normalization_handler import (
        TagNormalizationHandler,
    )
    uc = MagicMock()
    bus = MagicMock()
    return TagNormalizationHandler(use_case=uc, event_bus=bus), uc, bus


def _make_event(tag_groups=(("digital_twin", ["virtual replica"]),)):
    return AnalysisCompletedEvent(
        analysis_id=uuid.uuid4(),
        article_id=uuid.uuid4(),
        tag_groups=tag_groups,
    )


def test_publishes_completed_event_on_success():
    handler, uc, bus = _make_handler()
    uc.execute.return_value = NormalizeTagsResult(
        success=True, analysis_id=uuid.uuid4(), article_id=uuid.uuid4()
    )
    event = _make_event()
    handler.handle(event)

    bus.publish.assert_called_once()
    published = bus.publish.call_args[0][0]
    assert isinstance(published, TagNormalizationCompletedEvent)
    assert published.analysis_id == event.analysis_id


def test_publishes_failed_event_on_failure():
    handler, uc, bus = _make_handler()
    uc.execute.return_value = NormalizeTagsResult(
        success=False, analysis_id=uuid.uuid4(), article_id=uuid.uuid4(),
        exception_type="EmbeddingError", exception_message="quota exceeded",
    )
    event = _make_event()
    handler.handle(event)

    published = bus.publish.call_args[0][0]
    assert isinstance(published, TagNormalizationFailedEvent)
    assert published.exception_type == "EmbeddingError"
```

- [ ] **Step 2: Implement TagNormalizationHandler**

```python
# src/modules/intelligence/application/event_handlers/tag_normalization_handler.py
from src.shared.application.ports import EventBus
from src.shared.logging import get_logger
from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent,
    TagNormalizationCompletedEvent,
    TagNormalizationFailedEvent,
)
from src.modules.intelligence.application.use_cases.normalize_tags import NormalizeTagsUseCase

logger = get_logger(__name__)


class TagNormalizationHandler:

    def __init__(self, use_case: NormalizeTagsUseCase, event_bus: EventBus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    def handle(self, event: AnalysisCompletedEvent) -> None:
        result = self._use_case.execute(
            analysis_id=event.analysis_id,
            article_id=event.article_id,
            tag_groups=list(event.tag_groups),
        )

        if result.success:
            self._event_bus.publish(TagNormalizationCompletedEvent(
                analysis_id=event.analysis_id,
                article_id=event.article_id,
            ))
        else:
            self._event_bus.publish(TagNormalizationFailedEvent(
                analysis_id=event.analysis_id,
                article_id=event.article_id,
                exception_type=result.exception_type,
                exception_message=result.exception_message,
                traceback=result.traceback,
            ))
```

- [ ] **Step 3: Update ArticleProcessedHandler to carry tag_groups in event**

Replace `src/modules/intelligence/application/event_handlers/article_processed_handler.py`:

```python
from src.shared.application.events import ArticleProcessedEvent
from src.shared.application.ports import EventBus
from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase, AnalysisResult
from src.modules.intelligence.application.events import AnalysisCompletedEvent, AnalysisFailedEvent


class ArticleProcessedHandler:
    def __init__(self, use_case: AnalyzeArticleUseCase, event_bus: EventBus) -> None:
        self._use_case = use_case
        self._event_bus = event_bus

    def handle(self, event: ArticleProcessedEvent) -> None:
        result = self._use_case.execute(event.article)

        if result.success:
            raw_tag_groups = tuple(
                (tg.group_name, list(tg.tags))
                for tg in (result.analysis.analysis_content.tag_groups or [])
            )
            self._event_bus.publish(AnalysisCompletedEvent(
                analysis_id=result.analysis.id,
                article_id=result.article_id,
                tag_groups=raw_tag_groups,
            ))
        else:
            self._event_bus.publish(AnalysisFailedEvent(
                article_id=result.article_id,
                article_url=result.article_url,
                exception_type=result.exception_type,
                exception_message=result.exception_message,
            ))
```

- [ ] **Step 4: Rewire AnalysisCompletedHandler to TagNormalizationCompletedEvent + publish TranslationFailedEvent**

In `src/modules/intelligence/application/event_handlers/analysis_completed_handler.py`, update imports and signature:

```python
from src.shared.logging import get_logger
from src.modules.intelligence.application.events import (
    TagNormalizationCompletedEvent,
    TranslationFailedEvent,
)
from src.modules.intelligence.application.use_cases import TranslateArticleUseCase, TranslateTagsUseCase
from src.modules.intelligence.domain.repositories import AnalysesTranslationRepository
from src.shared.application.ports import EventBus

logger = get_logger(__name__)


class AnalysisCompletedHandler:
    """Translates article analysis and tags after tag normalization completes."""

    def __init__(
        self,
        translate_article_uc: TranslateArticleUseCase,
        translate_tags_uc: TranslateTagsUseCase,
        analyses_translation_repo: AnalysesTranslationRepository,
        event_bus: EventBus,
        target_languages: list[str] | None = None,
    ) -> None:
        self._translate_article_uc = translate_article_uc
        self._translate_tags_uc = translate_tags_uc
        self._analyses_translation_repo = analyses_translation_repo
        self._event_bus = event_bus
        self._target_languages = target_languages or ["zh-TW"]

    def handle(self, event: TagNormalizationCompletedEvent) -> None:
        en_content = self._analyses_translation_repo.find_by_analysis_id_and_language(
            event.analysis_id, 'en'
        )
        if not en_content:
            logger.warning("no_english_content_found", analysis_id=str(event.analysis_id))
            return

        for lang in self._target_languages:
            try:
                result = self._translate_article_uc.execute(
                    analysis_id=event.analysis_id,
                    summary=en_content.summary,
                    pain_points=en_content.pain_points,
                    insights=en_content.insights,
                    innovations=en_content.innovations,
                    target_language=lang,
                )
                if result.success:
                    logger.info("auto_translation_completed", analysis_id=str(event.analysis_id), language=lang)
                else:
                    self._event_bus.publish(TranslationFailedEvent(
                        analysis_id=event.analysis_id,
                        article_id=event.article_id,
                        task_type="translate_article",
                        exception_type="TranslationError",
                        exception_message=f"Translation failed for lang={lang}",
                        context={"language": lang},
                    ))
            except Exception as e:
                logger.error("auto_translation_error", analysis_id=str(event.analysis_id), language=lang, error=str(e))
                self._event_bus.publish(TranslationFailedEvent(
                    analysis_id=event.analysis_id,
                    article_id=event.article_id,
                    task_type="translate_article",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    context={"language": lang},
                ))

            try:
                self._translate_tags_uc.translate_tags(lang, limit=50)
            except Exception as e:
                logger.error("auto_tag_translation_error", language=lang, error=str(e))

            try:
                self._translate_tags_uc.translate_groups(lang, limit=50)
            except Exception as e:
                logger.error("auto_group_translation_error", language=lang, error=str(e))
```

- [ ] **Step 5: Remove tag-save block from analysis_repo_impl.save()**

In `src/infrastructure/persistence/intelligence/analysis_repo_impl.py`, delete the block starting with `# Resolve tag_groups into Tag rows` through the end of the `if article_row and content.tag_groups:` block. The `save()` method after this change ends at `self._session.commit()`.

The removed block is lines 52–71 (approximately):
```python
        # DELETE this entire block:
        article_row = self._session.query(ArticleModel).filter_by(
            id=analysis.article_id
        ).first()

        if article_row and content.tag_groups:
            for tg in content.tag_groups:
                group_name = tg.display_name
                for tag_name in tg.description.split(", "):
                    if not tag_name or not group_name:
                        continue
                    tag = self._session.query(Tag).filter_by(
                        name=tag_name, tag_group_name=group_name
                    ).first()
                    if not tag:
                        tag = Tag(name=tag_name, tag_group_name=group_name)
                        self._session.add(tag)
                        self._session.flush()
                    if tag not in article_row.tags:
                        article_row.tags.append(tag)
```

Also remove the unused `from models.tag import Tag` import from `save()`.

- [ ] **Step 6: Rewire bootstrap.py**

In `src/bootstrap.py`, update the use case assembly and event subscriptions:

Add imports at the top of `build_collection_pipeline()` (inside the function, with other imports):
```python
from src.modules.intelligence.application.use_cases import NormalizeTagsUseCase
from src.modules.intelligence.application.event_handlers import (
    ArticleScrapedHandler, ArticleProcessedHandler, AnalysisCompletedHandler,
)
from src.modules.intelligence.application.event_handlers.tag_normalization_handler import TagNormalizationHandler
from src.modules.intelligence.application.event_handlers.failed_task_persistence_handler import FailedTaskPersistenceHandler
from src.modules.intelligence.application.events import (
    AnalysisCompletedEvent, TagNormalizationCompletedEvent,
    AnalysisFailedEvent, TagNormalizationFailedEvent, TranslationFailedEvent,
)
from src.infrastructure.persistence.intelligence import SqlAlchemyTagRepository
from src.infrastructure.intelligence.embedding import GeminiEmbeddingProvider
```

Add `SqlAlchemyTagRepository` to the repositories block:
```python
    tag_repo = SqlAlchemyTagRepository(session=session)
```

Add embedding service build after LLM service:
```python
    # ── Embedding Service ────────────────────────────────────────────────────
    import os
    from src.config.providers import load_tag_normalization_config
    tag_norm_cfg = load_tag_normalization_config()
    embedding_service = GeminiEmbeddingProvider(
        api_key=os.environ.get(tag_norm_cfg['api_key_env'], ''),
        model=tag_norm_cfg['embedding_model'],
    )
```

Add `NormalizeTagsUseCase`:
```python
    normalize_tags_uc = NormalizeTagsUseCase(
        embedding_service=embedding_service,
        tag_repository=tag_repo,
        auto_merge_threshold=tag_norm_cfg['auto_merge_threshold'],
        suggest_threshold=tag_norm_cfg['suggest_threshold'],
    )
```

Update `AnalysisCompletedHandler` construction (now needs `event_bus`):
```python
    analysis_completed_handler = AnalysisCompletedHandler(
        translate_article_uc=translate_article_uc,
        translate_tags_uc=translate_tags_uc,
        analyses_translation_repo=analyses_translation_repo,
        event_bus=event_bus,
        target_languages=TRANSLATION_LANGUAGES,
    )
```

Add `TagNormalizationHandler`:
```python
    tag_normalization_handler = TagNormalizationHandler(
        use_case=normalize_tags_uc,
        event_bus=event_bus,
    )
```

Replace `AnalysisFailedHandler` with `FailedTaskPersistenceHandler`:
```python
    failed_task_handler = FailedTaskPersistenceHandler(failed_task_repository=failed_task_repo)
```

Update subscriptions:
```python
    event_bus.subscribe(AnalysisCompletedEvent, tag_normalization_handler.handle)
    event_bus.subscribe(TagNormalizationCompletedEvent, analysis_completed_handler.handle)
    event_bus.subscribe(AnalysisFailedEvent, failed_task_handler.handle)
    event_bus.subscribe(TagNormalizationFailedEvent, failed_task_handler.handle)
    event_bus.subscribe(TranslationFailedEvent, failed_task_handler.handle)
```

Remove the old `AnalysisFailedHandler` import and construction from `build_collection_pipeline()`.

Also add `load_tag_normalization_config` to `src/config/providers.py`:

In that file, add:
```python
def load_tag_normalization_config() -> dict:
    import tomllib, pathlib
    path = pathlib.Path("providers.toml")
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("tag_normalization", {
        "auto_merge_threshold": 0.92,
        "suggest_threshold": 0.85,
        "embedding_model": "text-embedding-004",
        "api_key_env": "GEMINI_API_KEY",
    })
```

- [ ] **Step 7: Run tests**

```bash
docker compose run --rm test_service pytest src/tests/unit/test_tag_normalization_handler.py src/tests/unit/test_composition_root.py -v
```

Expected: all pass.

- [ ] **Step 8: Run full test suite**

```bash
make test
```

Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add src/modules/intelligence/application/event_handlers/ \
        src/infrastructure/persistence/intelligence/analysis_repo_impl.py \
        src/bootstrap.py \
        src/config/providers.py \
        src/tests/unit/test_tag_normalization_handler.py
git commit -m "✨ [FEAT] TagNormalizationHandler, pipeline rewiring: AnalysisCompleted → Normalize → Translate"
```

---

## Task 12: Backfill Script

**Files:**
- Create: `scripts/backfill_tag_embeddings.py`

- [ ] **Step 1: Create backfill script**

```python
#!/usr/bin/env python
# scripts/backfill_tag_embeddings.py
"""
One-off script: embed all existing tags that have no embedding yet.

Usage:
    uv run python scripts/backfill_tag_embeddings.py [--limit N] [--dry-run]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max tags to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from src.shared.logging import get_logger
    logger = get_logger(__name__)

    from src.infrastructure.persistence.database import get_session, init_db
    from src.config.providers import load_tag_normalization_config
    from src.infrastructure.intelligence.embedding import GeminiEmbeddingProvider
    from sqlalchemy import text

    init_db()
    session = get_session()

    cfg = load_tag_normalization_config()
    provider = GeminiEmbeddingProvider(
        api_key=os.environ.get(cfg["api_key_env"], ""),
        model=cfg["embedding_model"],
    )

    # Fetch tags without embeddings
    query = "SELECT id, name FROM tags WHERE embedding IS NULL"
    if args.limit:
        query += f" LIMIT {args.limit}"
    rows = session.execute(text(query)).fetchall()

    logger.info("backfill_start", total=len(rows), dry_run=args.dry_run)

    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        tag_ids = [str(r[0]) for r in batch]
        tag_names = [r[1] for r in batch]

        vectors = provider.embed_batch(tag_names)

        if not args.dry_run:
            for tag_id, vec in zip(tag_ids, vectors):
                vec_str = "[" + ",".join(str(x) for x in vec) + "]"
                session.execute(
                    text("UPDATE tags SET embedding = CAST(:vec AS vector) WHERE id = :id"),
                    {"vec": vec_str, "id": tag_id},
                )
            session.commit()

        logger.info("backfill_batch_done", batch_start=i, count=len(batch))

    logger.info("backfill_complete", total=len(rows))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test dry-run locally**

```bash
docker compose run --rm job_service python scripts/backfill_tag_embeddings.py --dry-run --limit 5
```

Expected: logs `backfill_start`, `backfill_batch_done`, `backfill_complete` with no DB writes.

- [ ] **Step 3: Commit**

```bash
git add scripts/backfill_tag_embeddings.py
git commit -m "🛠️ [FEAT] backfill script: embed all existing tags with Gemini text-embedding-004"
```

---

## Task 13: Backend API — Tags Router

**Files:**
- Create: `backend/routers/tags.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create tags router**

```python
# backend/routers/tags.py
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.guards import require_admin, require_user

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class TagOut(BaseModel):
    id: UUID
    name: str
    article_count: int

    class Config:
        from_attributes = True


class TagGroupOut(BaseModel):
    id: UUID
    name: str
    display_name: str
    color_hex: Optional[str]
    topic_id: UUID
    tags: List[TagOut]

    class Config:
        from_attributes = True


class TagGroupCreate(BaseModel):
    name: str
    display_name: str
    color_hex: Optional[str] = None
    topic_id: UUID
    description: Optional[str] = None
    sort_order: Optional[int] = None


class TagGroupUpdate(BaseModel):
    display_name: Optional[str] = None
    color_hex: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class TagUpdate(BaseModel):
    name: str


class SuggestionOut(BaseModel):
    id: UUID
    new_tag_id: UUID
    new_tag_name: str
    existing_tag_id: UUID
    existing_tag_name: str
    group_name: str
    similarity_score: float
    article_id: Optional[UUID]

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tag_article_count(db: Session, tag_id: UUID) -> int:
    from sqlalchemy import text
    row = db.execute(
        text("SELECT COUNT(*) FROM article_tags WHERE tag_id = :id"),
        {"id": str(tag_id)},
    ).fetchone()
    return row[0] if row else 0


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/tag-groups", response_model=List[TagGroupOut])
def list_tag_groups(
    topic_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
):
    from models.tag_group import TagGroupDefinition
    from models.tag import Tag

    query = db.query(TagGroupDefinition)
    if topic_id:
        query = query.filter(TagGroupDefinition.topic_id == topic_id)
    groups = query.order_by(TagGroupDefinition.sort_order, TagGroupDefinition.display_name).all()

    result = []
    for grp in groups:
        tags = db.query(Tag).filter_by(tag_group_name=grp.name).order_by(Tag.name).all()
        tag_outs = [
            TagOut(id=t.id, name=t.name, article_count=_tag_article_count(db, t.id))
            for t in tags
        ]
        result.append(TagGroupOut(
            id=grp.id, name=grp.name, display_name=grp.display_name,
            color_hex=grp.color_hex, topic_id=grp.topic_id, tags=tag_outs,
        ))
    return result


@router.post("/tag-groups", response_model=TagGroupOut, status_code=201)
def create_tag_group(
    body: TagGroupCreate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    grp = TagGroupDefinition(**body.model_dump())
    db.add(grp)
    db.commit()
    db.refresh(grp)
    return TagGroupOut(id=grp.id, name=grp.name, display_name=grp.display_name,
                       color_hex=grp.color_hex, topic_id=grp.topic_id, tags=[])


@router.put("/tag-groups/{group_id}", response_model=TagGroupOut)
def update_tag_group(
    group_id: UUID,
    body: TagGroupUpdate,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    from models.tag import Tag
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="Tag group not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(grp, field, val)
    db.commit()
    db.refresh(grp)
    tags = db.query(Tag).filter_by(tag_group_name=grp.name).order_by(Tag.name).all()
    tag_outs = [TagOut(id=t.id, name=t.name, article_count=_tag_article_count(db, t.id)) for t in tags]
    return TagGroupOut(id=grp.id, name=grp.name, display_name=grp.display_name,
                       color_hex=grp.color_hex, topic_id=grp.topic_id, tags=tag_outs)


@router.delete("/tag-groups/{group_id}", status_code=204)
def delete_tag_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_group import TagGroupDefinition
    grp = db.query(TagGroupDefinition).filter_by(id=group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="Tag group not found")
    db.delete(grp)
    db.commit()


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
    tag.name = body.name
    db.commit()
    db.refresh(tag)
    return TagOut(id=tag.id, name=tag.name, article_count=_tag_article_count(db, tag.id))


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(
    tag_id: UUID,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag import Tag
    from sqlalchemy import text
    tag = db.query(Tag).filter_by(id=tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.execute(text("DELETE FROM article_tags WHERE tag_id = :id"), {"id": str(tag_id)})
    db.delete(tag)
    db.commit()


@router.get("/tag-normalization-suggestions", response_model=List[SuggestionOut])
def list_suggestions(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    from models.tag_normalization_suggestion import TagNormalizationSuggestion
    from models.tag import Tag
    rows = db.query(TagNormalizationSuggestion).filter_by(status="pending").all()
    result = []
    for r in rows:
        new_tag = db.query(Tag).filter_by(id=r.new_tag_id).first()
        existing_tag = db.query(Tag).filter_by(id=r.existing_tag_id).first()
        if not new_tag or not existing_tag:
            continue
        result.append(SuggestionOut(
            id=r.id, new_tag_id=r.new_tag_id, new_tag_name=new_tag.name,
            existing_tag_id=r.existing_tag_id, existing_tag_name=existing_tag.name,
            group_name=new_tag.tag_group_name, similarity_score=r.similarity_score,
            article_id=r.article_id,
        ))
    return result


@router.post("/tag-normalization-suggestions/{suggestion_id}/approve", status_code=200)
def approve_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    from src.infrastructure.persistence.intelligence.tag_repo_impl import SqlAlchemyTagRepository
    repo = SqlAlchemyTagRepository(session=db)
    repo.approve_suggestion(suggestion_id=suggestion_id, resolved_by=UUID(admin["sub"]))
    repo.commit()
    return {"status": "approved"}


@router.post("/tag-normalization-suggestions/{suggestion_id}/reject", status_code=200)
def reject_suggestion(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    from src.infrastructure.persistence.intelligence.tag_repo_impl import SqlAlchemyTagRepository
    repo = SqlAlchemyTagRepository(session=db)
    repo.reject_suggestion(suggestion_id=suggestion_id, resolved_by=UUID(admin["sub"]))
    repo.commit()
    return {"status": "rejected"}
```

- [ ] **Step 2: Register router in main.py**

In `backend/main.py`, add import and include:
```python
from backend.routers.tags import router as tags_router
```
And in the router registrations:
```python
app.include_router(tags_router)
```

- [ ] **Step 3: Start backend and verify endpoints**

```bash
docker compose up backend -d
curl -s http://localhost:8000/tag-groups | python -m json.tool | head -20
```

Expected: JSON array of tag groups (may be empty if DB is empty).

- [ ] **Step 4: Run backend tests**

```bash
uv run pytest backend/tests/ -v
```

Expected: existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/tags.py backend/main.py
git commit -m "✨ [FEAT] tags REST API: tag-groups CRUD, tag rename/delete, normalization suggestion approve/reject"
```

---

## Task 14: Frontend — Tags Page

**Files:**
- Create: `frontend/lib/api/tags.ts`
- Create: `frontend/components/features/tags/tag-group-card.tsx`
- Create: `frontend/components/features/tags/pending-suggestions.tsx`
- Create: `frontend/app/tags/page.tsx`
- Modify: `frontend/components/features/navigation/nav-bar.tsx`

- [ ] **Step 1: Create API client**

```typescript
// frontend/lib/api/tags.ts
import { apiFetch } from '@/lib/api-fetch'

export interface TagOut {
  id: string
  name: string
  article_count: number
}

export interface TagGroupOut {
  id: string
  name: string
  display_name: string
  color_hex: string | null
  topic_id: string
  tags: TagOut[]
}

export interface SuggestionOut {
  id: string
  new_tag_id: string
  new_tag_name: string
  existing_tag_id: string
  existing_tag_name: string
  group_name: string
  similarity_score: number
  article_id: string | null
}

export async function fetchTagGroups(topicId?: string): Promise<TagGroupOut[]> {
  const params = topicId ? `?topic_id=${topicId}` : ''
  return apiFetch(`/tag-groups${params}`)
}

export async function fetchPendingSuggestions(token: string): Promise<SuggestionOut[]> {
  return apiFetch('/tag-normalization-suggestions', { token })
}

export async function approveSuggestion(id: string, token: string): Promise<void> {
  await apiFetch(`/tag-normalization-suggestions/${id}/approve`, { method: 'POST', token })
}

export async function rejectSuggestion(id: string, token: string): Promise<void> {
  await apiFetch(`/tag-normalization-suggestions/${id}/reject`, { method: 'POST', token })
}

export async function renameTag(id: string, name: string, token: string): Promise<TagOut> {
  return apiFetch(`/tags/${id}`, { method: 'PUT', body: JSON.stringify({ name }), token })
}

export async function deleteTag(id: string, token: string): Promise<void> {
  await apiFetch(`/tags/${id}`, { method: 'DELETE', token })
}

export async function deleteTagGroup(id: string, token: string): Promise<void> {
  await apiFetch(`/tag-groups/${id}`, { method: 'DELETE', token })
}
```

- [ ] **Step 2: Create TagGroupCard component**

```tsx
// frontend/components/features/tags/tag-group-card.tsx
'use client'
import { useState } from 'react'
import { Pencil, X, Check, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { TagGroupOut, TagOut } from '@/lib/api/tags'
import { renameTag, deleteTag, deleteTagGroup } from '@/lib/api/tags'

interface Props {
  group: TagGroupOut
  isAdmin: boolean
  token?: string
  onDeleted: (groupId: string) => void
  onTagRenamed: (groupId: string, tagId: string, newName: string) => void
  onTagDeleted: (groupId: string, tagId: string) => void
}

function TagBadge({
  tag,
  isAdmin,
  token,
  groupId,
  onRenamed,
  onDeleted,
}: {
  tag: TagOut
  isAdmin: boolean
  token?: string
  groupId: string
  onRenamed: (tagId: string, name: string) => void
  onDeleted: (tagId: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(tag.name)

  async function handleRename() {
    if (!token || !value.trim()) return
    await renameTag(tag.id, value.trim(), token)
    onRenamed(tag.id, value.trim())
    setEditing(false)
  }

  async function handleDelete() {
    if (!token) return
    await deleteTag(tag.id, token)
    onDeleted(tag.id)
  }

  if (editing) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-border bg-background text-xs">
        <input
          className="w-24 bg-transparent text-xs focus:outline-none"
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleRename()}
          autoFocus
        />
        <button onClick={handleRename}><Check className="h-3 w-3 text-green-600" /></button>
        <button onClick={() => { setValue(tag.name); setEditing(false) }}><X className="h-3 w-3" /></button>
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-border bg-muted/50 text-xs">
      {tag.name}
      <span className="text-muted-foreground">({tag.article_count})</span>
      {isAdmin && (
        <>
          <button onClick={() => setEditing(true)} className="hover:text-foreground text-muted-foreground">
            <Pencil className="h-2.5 w-2.5" />
          </button>
          <button onClick={handleDelete} className="hover:text-destructive text-muted-foreground">
            <X className="h-2.5 w-2.5" />
          </button>
        </>
      )}
    </span>
  )
}

export function TagGroupCard({ group, isAdmin, token, onDeleted, onTagRenamed, onTagDeleted }: Props) {
  const [tags, setTags] = useState<TagOut[]>(group.tags)

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {group.color_hex && (
            <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: group.color_hex }} />
          )}
          <span className="font-semibold text-sm">{group.display_name}</span>
          <span className="text-xs text-muted-foreground">({tags.length} tags)</span>
        </div>
        {isAdmin && token && (
          <Button
            variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={async () => { await deleteTagGroup(group.id, token); onDeleted(group.id) }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {tags.map(tag => (
          <TagBadge
            key={tag.id}
            tag={tag}
            isAdmin={isAdmin}
            token={token}
            groupId={group.id}
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
        {tags.length === 0 && (
          <span className="text-xs text-muted-foreground italic">No tags yet</span>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create PendingSuggestions component**

```tsx
// frontend/components/features/tags/pending-suggestions.tsx
'use client'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { SuggestionOut } from '@/lib/api/tags'
import { approveSuggestion, rejectSuggestion } from '@/lib/api/tags'

interface Props {
  suggestions: SuggestionOut[]
  token: string
  onResolved: (id: string) => void
}

export function PendingSuggestions({ suggestions, token, onResolved }: Props) {
  const [processing, setProcessing] = useState<string | null>(null)

  if (suggestions.length === 0) return null

  async function handle(id: string, action: 'approve' | 'reject') {
    setProcessing(id)
    try {
      if (action === 'approve') await approveSuggestion(id, token)
      else await rejectSuggestion(id, token)
      onResolved(id)
    } finally {
      setProcessing(null)
    }
  }

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/20 p-5 space-y-3">
      <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-200">
        Pending Merge Suggestions ({suggestions.length})
      </h3>
      <div className="space-y-2">
        {suggestions.map(s => (
          <div key={s.id} className="flex items-center justify-between gap-3 text-sm">
            <div className="min-w-0">
              <span className="font-medium">&ldquo;{s.new_tag_name}&rdquo;</span>
              <span className="text-muted-foreground mx-1">→</span>
              <span className="font-medium">&ldquo;{s.existing_tag_name}&rdquo;</span>
              <span className="text-muted-foreground ml-2 text-xs">
                {s.group_name} · {(s.similarity_score * 100).toFixed(0)}% similar
              </span>
            </div>
            <div className="flex gap-1.5 shrink-0">
              <Button
                size="sm" variant="outline" className="h-7 px-2 text-xs"
                disabled={processing === s.id}
                onClick={() => handle(s.id, 'approve')}
              >
                Merge
              </Button>
              <Button
                size="sm" variant="ghost" className="h-7 px-2 text-xs text-muted-foreground"
                disabled={processing === s.id}
                onClick={() => handle(s.id, 'reject')}
              >
                Keep both
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create /tags page**

```tsx
// frontend/app/tags/page.tsx
'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Skeleton } from '@/components/ui/skeleton'
import { useTopic } from '@/lib/providers'
import {
  fetchTagGroups, fetchPendingSuggestions,
  type TagGroupOut, type SuggestionOut,
} from '@/lib/api/tags'
import { TagGroupCard } from '@/components/features/tags/tag-group-card'
import { PendingSuggestions } from '@/components/features/tags/pending-suggestions'

export default function TagsPage() {
  const { data: session } = useSession()
  const token = (session as any)?.accessToken as string | undefined
  const isAdmin = (session?.user as any)?.role === 'admin'
  const { selectedTopic } = useTopic()

  const [groups, setGroups] = useState<TagGroupOut[]>([])
  const [suggestions, setSuggestions] = useState<SuggestionOut[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const topicId = selectedTopic?.id
    Promise.all([
      fetchTagGroups(topicId),
      isAdmin && token ? fetchPendingSuggestions(token) : Promise.resolve([]),
    ])
      .then(([g, s]) => { setGroups(g); setSuggestions(s) })
      .finally(() => setLoading(false))
  }, [selectedTopic?.id, isAdmin, token])

  return (
    <div className="container mx-auto px-6 pt-24 pb-16 max-w-4xl space-y-8">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">Tags</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse tag groups and their articles.
          {isAdmin && ' Admins can rename, delete, and merge tags.'}
        </p>
      </div>

      {isAdmin && suggestions.length > 0 && (
        <PendingSuggestions
          suggestions={suggestions}
          token={token!}
          onResolved={id => setSuggestions(prev => prev.filter(s => s.id !== id))}
        />
      )}

      {loading ? (
        <div className="space-y-4">
          {[0, 1, 2].map(i => (
            <div key={i} className="rounded-xl border border-border bg-card p-5 space-y-3">
              <Skeleton className="h-4 w-32" />
              <div className="flex gap-2">
                <Skeleton className="h-6 w-20 rounded-full" />
                <Skeleton className="h-6 w-16 rounded-full" />
                <Skeleton className="h-6 w-24 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      ) : groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No tag groups found for this topic.</p>
      ) : (
        <div className="space-y-4">
          {groups.map(group => (
            <TagGroupCard
              key={group.id}
              group={group}
              isAdmin={isAdmin}
              token={token}
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
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Add Tags link to NavBar**

In `frontend/components/features/navigation/nav-bar.tsx`, in the "Left nav" section, add after the Knowledge Graph link:

```tsx
          <Link
            href="/tags"
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors duration-200 ${
              pathname === '/tags'
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            {t('nav.tags')}
          </Link>
```

Also add the i18n key: in `frontend/i18n/en.json` (and `zh-TW.json`) add `"nav": { "tags": "Tags" }` (merge with existing `nav` object).

- [ ] **Step 6: Start dev server and verify**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/tags`. Verify:
- Tags link appears in navbar
- Page loads without errors
- Tag group cards render (if DB has data)
- Admin sees pending suggestions section (if logged in as admin)

- [ ] **Step 7: Run frontend tests**

```bash
cd frontend && npm run test
```

Expected: existing tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/api/tags.ts \
        frontend/components/features/tags/ \
        frontend/app/tags/ \
        frontend/components/features/navigation/nav-bar.tsx \
        frontend/i18n/
git commit -m "✨ [FEAT] /tags page: tag group cards, pending merge suggestions, admin CRUD"
```
