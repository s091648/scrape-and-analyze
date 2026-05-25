# Tag Mode Three-Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the boolean `auto_tag_groups` field on `Topic` with a three-value `tag_mode` enum (`unsupervised | semi_supervised | supervised`) so admins can control LLM tag generation granularity per topic.

**Architecture:** A new `TagMode` enum flows from DB → ORM model → domain entity → repository → use case → prompt template. The analysis use case's `_build_prompt` gains a third branch (semi-supervised renders a hint-based prompt with existing groups). Frontend replaces a boolean switch with a `TagModeSelector` segmented control reused in two pages.

**Tech Stack:** Python 3.11, SQLAlchemy, Alembic, FastAPI/Pydantic, Next.js 15, React 19, Radix UI Tabs, Storybook, pytest, Vitest

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/shared/domain/value_objects/tag_mode.py` | `TagMode` enum definition |
| Modify | `src/shared/domain/value_objects/__init__.py` | Export `TagMode` |
| Modify | `src/shared/domain/entities/topic.py` | Replace `auto_tag_groups: bool` with `tag_mode: TagMode` |
| Create | `alembic/versions/19_tag_mode.py` | DB migration: add column, backfill, drop old |
| Modify | `models/topic.py` | Replace ORM column |
| Modify | `src/infrastructure/persistence/shared/topic_repo_impl.py` | Update `_to_entity` mapping |
| Modify | `src/modules/intelligence/domain/value_objects/analysis_prompt.py` | Add `_SEMI_TEMPLATE` + `render_semi` |
| Modify | `src/modules/intelligence/application/use_cases/analyze_article.py` | Three-tier `_build_prompt` + upsert guard |
| Modify | `backend/schemas/topic.py` | Replace `auto_tag_groups` in all three schemas |
| Modify | `frontend/lib/api/topics.ts` | Update `Topic` interface |
| Modify | `frontend/lib/providers/locales/en.json` | Add tag mode translation keys |
| Modify | `frontend/lib/providers/locales/zh-TW.json` | Add tag mode translation keys |
| Create | `frontend/components/features/tags/tag-mode-selector.tsx` | Segmented control component |
| Create | `frontend/stories/TagModeSelector.stories.tsx` | Storybook stories |
| Modify | `frontend/app/tags/page.tsx` | Replace boolean switch with `TagModeSelector` |
| Modify | `frontend/app/admin/topics/page.tsx` | Add `TagModeSelector` to edit + create forms |
| Create | `src/tests/unit/shared/domain/test_tag_mode.py` | Unit tests for `TagMode` |
| Modify | `src/tests/unit/shared/domain/test_topic_entity.py` | Update `test_topic_defaults` |
| Modify | `src/tests/unit/infrastructure/persistence/shared/test_topic_repo.py` | Update mock + add tag_mode assertion |
| Modify | `src/tests/unit/infrastructure/persistence/test_models.py` | Replace `auto_tag_groups` column assertion |
| Create | `src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py` | Tests for `render_semi` |
| Modify | `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py` | Update tag_mode references + add semi tests |

---

## Task 1: TagMode enum value object

**Files:**
- Create: `src/shared/domain/value_objects/tag_mode.py`
- Modify: `src/shared/domain/value_objects/__init__.py`
- Create: `src/tests/unit/shared/domain/test_tag_mode.py`

- [ ] **Step 1: Write the failing tests**

Create `src/tests/unit/shared/domain/test_tag_mode.py`:

```python
def test_tag_mode_values():
    from src.shared.domain.value_objects.tag_mode import TagMode
    assert TagMode.UNSUPERVISED == 'unsupervised'
    assert TagMode.SEMI_SUPERVISED == 'semi_supervised'
    assert TagMode.SUPERVISED == 'supervised'


def test_tag_mode_is_str():
    from src.shared.domain.value_objects.tag_mode import TagMode
    assert isinstance(TagMode.UNSUPERVISED, str)


def test_tag_mode_from_string():
    from src.shared.domain.value_objects.tag_mode import TagMode
    assert TagMode('unsupervised') is TagMode.UNSUPERVISED
    assert TagMode('semi_supervised') is TagMode.SEMI_SUPERVISED
    assert TagMode('supervised') is TagMode.SUPERVISED
```

- [ ] **Step 2: Run tests to verify they fail**

```
docker compose exec test_service uv run pytest src/tests/unit/shared/domain/test_tag_mode.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` (file doesn't exist yet)

- [ ] **Step 3: Create `src/shared/domain/value_objects/tag_mode.py`**

```python
from enum import Enum


class TagMode(str, Enum):
    UNSUPERVISED = 'unsupervised'
    SEMI_SUPERVISED = 'semi_supervised'
    SUPERVISED = 'supervised'
```

- [ ] **Step 4: Export from `src/shared/domain/value_objects/__init__.py`**

The file currently contains only a blank line. Replace with:

```python
from .tag_mode import TagMode

__all__ = ["TagMode"]
```

- [ ] **Step 5: Run tests to verify they pass**

```
docker compose exec test_service uv run pytest src/tests/unit/shared/domain/test_tag_mode.py -v
```

Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/shared/domain/value_objects/tag_mode.py src/shared/domain/value_objects/__init__.py src/tests/unit/shared/domain/test_tag_mode.py
git commit -m "$(cat <<'EOF'
🏷️ [FEAT] add TagMode enum value object

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Topic domain entity update

**Files:**
- Modify: `src/shared/domain/entities/topic.py`
- Modify: `src/tests/unit/shared/domain/test_topic_entity.py`

- [ ] **Step 1: Update the test to assert `tag_mode` instead of `auto_tag_groups`**

Replace the contents of `src/tests/unit/shared/domain/test_topic_entity.py`:

```python
def test_topic_defaults():
    from src.shared.domain.entities import Topic
    from src.shared.domain.value_objects.tag_mode import TagMode
    t = Topic(name="digital-twins", display_name="Digital Twins")
    assert t.id is None
    assert t.is_active is True
    assert t.prompt_override is None
    assert t.color_hex is None
    assert t.tag_mode == TagMode.UNSUPERVISED
```

- [ ] **Step 2: Run test to verify it fails**

```
docker compose exec test_service uv run pytest src/tests/unit/shared/domain/test_topic_entity.py -v
```

Expected: `AttributeError: 'Topic' object has no attribute 'tag_mode'`

- [ ] **Step 3: Update `src/shared/domain/entities/topic.py`**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.shared.domain.value_objects.tag_mode import TagMode


@dataclass
class Topic:
    name: str
    display_name: str
    id: Optional[UUID] = None
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: bool = True
    tag_mode: TagMode = TagMode.UNSUPERVISED
    created_at: Optional[datetime] = None
```

- [ ] **Step 4: Run tests to verify they pass**

```
docker compose exec test_service uv run pytest src/tests/unit/shared/domain/ -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/shared/domain/entities/topic.py src/tests/unit/shared/domain/test_topic_entity.py
git commit -m "$(cat <<'EOF'
🏷️ [FEAT] replace auto_tag_groups with tag_mode on Topic entity

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: ORM model + Alembic migration

**Files:**
- Modify: `models/topic.py`
- Create: `alembic/versions/19_tag_mode.py`
- Modify: `src/tests/unit/infrastructure/persistence/test_models.py`

- [ ] **Step 1: Update test_models.py — replace auto_tag_groups assertion**

In `src/tests/unit/infrastructure/persistence/test_models.py`, find the section that tests the `Topic` model. There is no existing explicit `auto_tag_groups` test there, so add a new test at the end of the file:

```python
def test_topic_model_has_tag_mode_column():
    from models.topic import Topic
    assert hasattr(Topic, 'tag_mode')
    col = Topic.__table__.columns['tag_mode']
    assert str(col.type) == 'VARCHAR(20)'


def test_topic_model_has_no_auto_tag_groups_column():
    from models.topic import Topic
    assert 'auto_tag_groups' not in Topic.__table__.columns
```

- [ ] **Step 2: Run tests to verify they fail**

```
docker compose exec test_service uv run pytest src/tests/unit/infrastructure/persistence/test_models.py::test_topic_model_has_tag_mode_column src/tests/unit/infrastructure/persistence/test_models.py::test_topic_model_has_no_auto_tag_groups_column -v
```

Expected: both FAIL (column doesn't exist yet)

- [ ] **Step 3: Update `models/topic.py`**

Replace `auto_tag_groups` column:

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Topic(Base):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    color_hex = Column(String(7))
    prompt_override = Column(Text)
    sort_order = Column(Integer)
    is_active = Column(Boolean, nullable=False, default=True)
    tag_mode = Column(String(20), nullable=False, default='unsupervised')
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_topics_name", "name"),
    )
```

- [ ] **Step 4: Create `alembic/versions/19_tag_mode.py`**

```python
"""replace_auto_tag_groups_with_tag_mode

Replace the boolean auto_tag_groups column on topics with a tag_mode
VARCHAR(20) column supporting 'unsupervised', 'semi_supervised', 'supervised'.

Revision ID: 19_tag_mode
Revises: 18_add_data_migrations_table
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision: str = "19_tag_mode"
down_revision = "18_add_data_migrations_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("tag_mode", sa.String(20), nullable=False, server_default="unsupervised"),
    )
    op.execute(
        "UPDATE topics SET tag_mode = CASE WHEN auto_tag_groups = TRUE "
        "THEN 'unsupervised' ELSE 'supervised' END"
    )
    op.alter_column("topics", "tag_mode", server_default=None)
    op.drop_column("topics", "auto_tag_groups")


def downgrade() -> None:
    op.add_column(
        "topics",
        sa.Column(
            "auto_tag_groups",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        "UPDATE topics SET auto_tag_groups = CASE WHEN tag_mode = 'supervised' "
        "THEN FALSE ELSE TRUE END"
    )
    op.alter_column("topics", "auto_tag_groups", server_default=None)
    op.drop_column("topics", "tag_mode")
```

- [ ] **Step 5: Run model unit tests**

```
docker compose exec test_service uv run pytest src/tests/unit/infrastructure/persistence/test_models.py -v
```

Expected: all PASSED (ORM model tests don't hit DB, just inspect column definitions)

- [ ] **Step 6: Run migration locally**

```
make migrate
```

Expected: `Running upgrade 18_add_data_migrations_table -> 19_tag_mode, replace_auto_tag_groups_with_tag_mode`

- [ ] **Step 7: Commit**

```bash
git add models/topic.py alembic/versions/19_tag_mode.py src/tests/unit/infrastructure/persistence/test_models.py
git commit -m "$(cat <<'EOF'
🗄️ [FEAT] replace auto_tag_groups with tag_mode column (migration 19)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Topic repository update

**Files:**
- Modify: `src/infrastructure/persistence/shared/topic_repo_impl.py`
- Modify: `src/tests/unit/infrastructure/persistence/shared/test_topic_repo.py`

- [ ] **Step 1: Update test mock and add tag_mode assertion**

Replace the contents of `src/tests/unit/infrastructure/persistence/shared/test_topic_repo.py`:

```python
from unittest.mock import MagicMock
from uuid import uuid4

from src.shared.domain.value_objects.tag_mode import TagMode


def _make_topic_row(name="digital-twins"):
    row = MagicMock()
    row.id = uuid4()
    row.name = name
    row.display_name = "Digital Twins"
    row.description = None
    row.color_hex = "#3B82F6"
    row.prompt_override = None
    row.sort_order = 1
    row.is_active = True
    row.tag_mode = 'unsupervised'
    row.created_at = None
    return row


def test_list_active_returns_entities():
    from src.infrastructure.persistence.shared.topic_repo_impl import (
        SqlAlchemyTopicRepository,
    )
    from src.shared.domain.entities import Topic
    row = _make_topic_row()
    session = MagicMock()
    session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [row]
    repo = SqlAlchemyTopicRepository(session=session)
    results = repo.list_active()
    assert len(results) == 1
    assert isinstance(results[0], Topic)
    assert results[0].name == "digital-twins"


def test_find_by_id_returns_none_when_not_found():
    from src.infrastructure.persistence.shared.topic_repo_impl import (
        SqlAlchemyTopicRepository,
    )
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    repo = SqlAlchemyTopicRepository(session=session)
    assert repo.find_by_id(uuid4()) is None


def test_to_entity_maps_tag_mode():
    from src.infrastructure.persistence.shared.topic_repo_impl import (
        SqlAlchemyTopicRepository,
    )
    row = _make_topic_row()
    row.tag_mode = 'semi_supervised'
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = row
    repo = SqlAlchemyTopicRepository(session=session)
    topic = repo.find_by_id(row.id)
    assert topic.tag_mode == TagMode.SEMI_SUPERVISED
```

- [ ] **Step 2: Run tests to verify they fail**

```
docker compose exec test_service uv run pytest src/tests/unit/infrastructure/persistence/shared/test_topic_repo.py -v
```

Expected: `test_to_entity_maps_tag_mode` FAIL (repo still reads `auto_tag_groups`)

- [ ] **Step 3: Update `src/infrastructure/persistence/shared/topic_repo_impl.py`**

```python
from typing import List, Optional
from uuid import UUID

from src.shared.domain.entities import Topic
from src.shared.domain.repositories import TopicRepository
from src.shared.domain.value_objects.tag_mode import TagMode
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTopicRepository(TopicRepository):

    def __init__(self, session) -> None:
        self._session = session

    def list_active(self) -> List[Topic]:
        from models.topic import Topic as TopicModel

        rows = (
            self._session.query(TopicModel)
            .filter_by(is_active=True)
            .order_by(TopicModel.sort_order)
            .all()
        )
        return [self._to_entity(r) for r in rows]

    def find_by_id(self, topic_id: UUID) -> Optional[Topic]:
        from models.topic import Topic as TopicModel

        row = self._session.query(TopicModel).filter_by(id=topic_id).first()
        return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row) -> Topic:
        return Topic(
            id=row.id,
            name=row.name,
            display_name=row.display_name,
            description=row.description,
            color_hex=row.color_hex,
            prompt_override=row.prompt_override,
            sort_order=row.sort_order,
            is_active=row.is_active,
            tag_mode=TagMode(row.tag_mode),
            created_at=row.created_at,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```
docker compose exec test_service uv run pytest src/tests/unit/infrastructure/persistence/shared/test_topic_repo.py -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/persistence/shared/topic_repo_impl.py src/tests/unit/infrastructure/persistence/shared/test_topic_repo.py
git commit -m "$(cat <<'EOF'
🔄 [FEAT] update topic repo to map tag_mode enum

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Analysis prompt — semi-supervised template

**Files:**
- Modify: `src/modules/intelligence/domain/value_objects/analysis_prompt.py`
- Create: `src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py`

- [ ] **Step 1: Write failing tests**

Create `src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py`:

```python
from src.modules.intelligence.domain.value_objects import AnalysisPrompt, TagGroup


def _groups():
    return [
        TagGroup(name="research_methods", display_name="Research Methods", description=""),
        TagGroup(name="applications", display_name="Applications", description="Practical uses"),
    ]


def test_render_semi_fills_topic():
    prompt = AnalysisPrompt()
    rendered = prompt.render_semi(topic="AI", tag_groups=_groups())
    assert "AI" in rendered.content


def test_render_semi_includes_existing_group_names():
    prompt = AnalysisPrompt()
    rendered = prompt.render_semi(topic="AI", tag_groups=_groups())
    assert "research_methods" in rendered.content
    assert "applications" in rendered.content


def test_render_semi_allows_new_groups_in_instructions():
    prompt = AnalysisPrompt()
    rendered = prompt.render_semi(topic="AI", tag_groups=_groups())
    assert "new" in rendered.content.lower() or "create" in rendered.content.lower()


def test_render_semi_returns_analysis_prompt_instance():
    prompt = AnalysisPrompt()
    result = prompt.render_semi(topic="AI", tag_groups=_groups())
    assert isinstance(result, AnalysisPrompt)


def test_render_semi_with_empty_groups_still_renders():
    prompt = AnalysisPrompt()
    rendered = prompt.render_semi(topic="AI", tag_groups=[])
    assert "AI" in rendered.content
```

- [ ] **Step 2: Run tests to verify they fail**

```
docker compose exec test_service uv run pytest src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py -v
```

Expected: all FAIL with `AttributeError: 'AnalysisPrompt' object has no attribute 'render_semi'`

- [ ] **Step 3: Add `_SEMI_TEMPLATE` and `render_semi` to `analysis_prompt.py`**

In `src/modules/intelligence/domain/value_objects/analysis_prompt.py`, add after `_FIXED_TEMPLATE`:

```python
# ── Semi-supervised mode: LLM sees existing groups as hints, may create new ──

_SEMI_TEMPLATE = """You are a professional technology analyst specializing in __TOPIC__.

Analyze the following article and classify it into relevant tag groups.
The following tag groups already exist for this topic — prefer reusing them when they fit,
but you may also create new snake_case groups if the article covers something genuinely different:

EXISTING TAG GROUPS:
__TAG_GROUPS__

For each applicable group, generate 2-4 specific sub-tags describing the article's focus.
Assign 1-3 groups total; only include groups truly relevant to the article.
If none of the existing groups fit well, feel free to create new snake_case group keys.
""" + _COMMON_EXTRACTION
```

Then add `render_semi` method inside the `AnalysisPrompt` class, after `render_fixed`:

```python
    def render_semi(self, topic: str, tag_groups: List[TagGroup]) -> 'AnalysisPrompt':
        """Fill __TOPIC__ and __TAG_GROUPS__; LLM may reuse or create new groups."""
        filled = _SEMI_TEMPLATE.replace("__TOPIC__", topic)
        filled = filled.replace("__TAG_GROUPS__", self._format_fixed_groups(tag_groups))
        return AnalysisPrompt(_content=filled)
```

- [ ] **Step 4: Run tests to verify they pass**

```
docker compose exec test_service uv run pytest src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/modules/intelligence/domain/value_objects/analysis_prompt.py src/tests/unit/modules/intelligence/domain/test_analysis_prompt.py
git commit -m "$(cat <<'EOF'
🧠 [FEAT] add semi-supervised prompt template and render_semi method

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Analyze article use case — three-tier logic

**Files:**
- Modify: `src/modules/intelligence/application/use_cases/analyze_article.py`
- Modify: `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py`

- [ ] **Step 1: Update existing test that uses `auto_tag_groups`**

In `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py`, find `test_upsert_generates_embedding_for_new_tag_groups` (around line 124). Change line:

```python
    topic.auto_tag_groups = True
```

to:

```python
    topic.tag_mode = 'unsupervised'
```

- [ ] **Step 2: Add new tests for semi-supervised and supervised prompt selection**

Append to `src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py`:

```python
def test_build_prompt_uses_supervised_template_when_tag_mode_supervised(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.domain.repositories import TagGroupDefinitionRepository

    topic = MagicMock()
    topic.display_name = "AI"
    topic.tag_mode = 'supervised'
    deps["topic_repository"].find_by_id.return_value = topic

    group = MagicMock()
    group.name = "research_methods"
    group.display_name = "Research Methods"
    group.description = ""
    deps["tag_group_definition_repository"].find_by_topic_id.return_value = [group]
    deps["llm_service"].analyze.return_value = _make_llm_result()

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    called_prompt = deps["llm_service"].analyze.call_args[0][1]
    assert "research_methods" in called_prompt
    assert "ONLY these exact key strings" in called_prompt


def test_build_prompt_uses_semi_supervised_template_when_tag_mode_semi(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase

    topic = MagicMock()
    topic.display_name = "AI"
    topic.tag_mode = 'semi_supervised'
    deps["topic_repository"].find_by_id.return_value = topic

    group = MagicMock()
    group.name = "applications"
    group.display_name = "Applications"
    group.description = ""
    deps["tag_group_definition_repository"].find_by_topic_id.return_value = [group]
    deps["llm_service"].analyze.return_value = _make_llm_result()

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    called_prompt = deps["llm_service"].analyze.call_args[0][1]
    assert "applications" in called_prompt
    assert "EXISTING TAG GROUPS" in called_prompt


def test_supervised_mode_does_not_upsert_tag_groups(deps):
    from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase
    from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata, AnalysisTagGroup

    topic = MagicMock()
    topic.display_name = "AI"
    topic.tag_mode = 'supervised'
    deps["topic_repository"].find_by_id.return_value = topic

    group = MagicMock()
    group.name = "research_methods"
    group.display_name = "Research Methods"
    group.description = ""
    deps["tag_group_definition_repository"].find_by_topic_id.return_value = [group]

    tag_groups = [AnalysisTagGroup(group_name="new_group", tags=["tag1"])]
    content = AnalysisContent(
        tag_groups=tag_groups, pain_points="p", insights="i", innovations="n", summary="s"
    )
    deps["llm_service"].analyze.return_value = (
        content,
        AnalysisMetadata(model_used="test", input_tokens=1, output_tokens=1),
    )

    uc = AnalyzeArticleUseCase(**deps, prompt=AnalysisPrompt())
    uc.execute(_make_article(topic_id=uuid.uuid4()))

    deps["tag_group_definition_repository"].upsert.assert_not_called()
```

- [ ] **Step 3: Run tests to verify new ones fail**

```
docker compose exec test_service uv run pytest src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py -v
```

Expected: the three new tests FAIL; the updated `test_upsert_generates_embedding_for_new_tag_groups` should still pass since MagicMock accepts any attribute.

- [ ] **Step 4: Update `analyze_article.py`**

Replace the full file contents:

```python
from typing import List, Optional
from uuid import UUID

from src.shared.domain.entities import Article
from src.shared.domain.repositories import TopicRepository
from src.shared.domain.value_objects.tag_mode import TagMode
from src.shared.logging import get_logger
from src.modules.intelligence.domain.entities import Analysis
from src.modules.intelligence.domain.repositories import (
    AnalysisRepository,
    TagGroupDefinitionRepository,
)
from src.modules.intelligence.domain.services import LLMService, EmbeddingService
from src.modules.intelligence.domain.value_objects import AnalysisPrompt, TagGroup, AnalysisTagGroup
from src.modules.intelligence.application.use_cases import AnalysisResult

logger = get_logger(__name__)


class AnalyzeArticleUseCase:
    def __init__(
        self,
        llm_service: LLMService,
        analysis_repository: AnalysisRepository,
        topic_repository: TopicRepository,
        tag_group_definition_repository: TagGroupDefinitionRepository,
        prompt: AnalysisPrompt,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self._llm_service = llm_service
        self._analysis_repository = analysis_repository
        self._topic_repository = topic_repository
        self._tag_group_definition_repository = tag_group_definition_repository
        self._prompt = prompt
        self._embedding_service = embedding_service

    def execute(self, article: Article) -> AnalysisResult:
        content = article.get_analysis_content()
        prompt = self._build_prompt(article.topic_id)
        result = self._llm_service.analyze(content, prompt)

        if result is None:
            logger.error("llm_analysis_failed", article_id=str(article.id))
            return AnalysisResult(
                success=False,
                article_id=article.id,
                article_url=article.url,
                exception_type="LLMAnalysisError",
                exception_message="All LLM providers returned None",
            )

        analysis_content, analysis_metadata = result

        if article.topic_id is not None:
            topic = self._topic_repository.find_by_id(article.topic_id)
            if topic is not None and topic.tag_mode != TagMode.SUPERVISED:
                self._upsert_generated_tag_groups(
                    analysis_content.tag_groups or [],
                    article.topic_id,
                )

        analysis = Analysis(
            article_id=article.id,
            analysis_content=analysis_content,
            analysis_metadata=analysis_metadata,
        )

        try:
            self._analysis_repository.save(analysis)
        except Exception as e:
            logger.error("analysis_save_failed", article_id=str(article.id), error=str(e))
            return AnalysisResult(
                success=False,
                article_id=article.id,
                article_url=article.url,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        logger.info(
            "analysis_completed",
            article_id=str(article.id),
            model=analysis_metadata.model_used,
            input_tokens=analysis_metadata.input_tokens,
            output_tokens=analysis_metadata.output_tokens,
        )

        return AnalysisResult(
            success=True,
            article_id=article.id,
            article_url=article.url,
            analysis=analysis,
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _build_prompt(self, topic_id: Optional[UUID]) -> str:
        """
        Render an AnalysisPrompt for the article's topic.

        Priority:
          1. article has a topic_id + topic found in DB
               → supervised:      render_fixed (constrained to predefined groups)
               → semi_supervised: render_semi  (existing groups as hints, new allowed)
               → unsupervised:    render_auto  (LLM generates freely)
          2. no topic_id → render_auto with all active topics merged
          3. no topics in DB → return unrendered auto template
        """
        if topic_id is not None:
            topic = self._topic_repository.find_by_id(topic_id)
            if topic is not None:
                if topic.tag_mode == TagMode.SUPERVISED:
                    db_groups = self._tag_group_definition_repository.find_by_topic_id(topic_id)
                    if db_groups:
                        tag_groups = [
                            TagGroup(name=g.name, display_name=g.display_name, description=g.description or "")
                            for g in db_groups
                        ]
                        return self._prompt.render_fixed(
                            topic=topic.display_name,
                            tag_groups=tag_groups,
                        ).content
                    logger.warning(
                        "supervised_mode_no_groups_falling_back_to_auto",
                        topic_id=str(topic_id),
                    )

                elif topic.tag_mode == TagMode.SEMI_SUPERVISED:
                    db_groups = self._tag_group_definition_repository.find_by_topic_id(topic_id)
                    if db_groups:
                        tag_groups = [
                            TagGroup(name=g.name, display_name=g.display_name, description=g.description or "")
                            for g in db_groups
                        ]
                        return self._prompt.render_semi(
                            topic=topic.display_name,
                            tag_groups=tag_groups,
                        ).content

                return self._prompt.render_auto(topic=topic.display_name).content

        topics = self._topic_repository.list_active()
        if not topics:
            logger.warning("no_active_topics_using_unrendered_prompt")
            return self._prompt.content

        topic_str = ", ".join(t.display_name for t in topics)
        return self._prompt.render_auto(topic=topic_str).content

    def _upsert_generated_tag_groups(
        self,
        tag_groups: List[AnalysisTagGroup],
        topic_id: UUID,
    ) -> None:
        """Persist LLM-generated tag group keys as TagGroupDefinition rows (unsupervised + semi mode)."""
        valid = [(tg, tg.group_name) for tg in tag_groups if tg.group_name]
        if not valid:
            return

        embeddings: List[Optional[List[float]]] = [None] * len(valid)
        if self._embedding_service is not None:
            try:
                texts = [
                    f"{gk} - {gk.replace('_', ' ').title()}"
                    for _, gk in valid
                ]
                embeddings = self._embedding_service.embed_batch(texts)
            except Exception as e:
                logger.warning("tag_group_embedding_failed", error=str(e))

        for (tg, group_key), embedding in zip(valid, embeddings):
            display_name = group_key.replace("_", " ").title()
            try:
                self._tag_group_definition_repository.upsert(
                    name=group_key,
                    display_name=display_name,
                    topic_id=topic_id,
                    embedding=embedding,
                )
            except Exception as e:
                logger.warning(
                    "tag_group_definition_upsert_failed",
                    group=group_key,
                    topic_id=str(topic_id),
                    error=str(e),
                )
```

- [ ] **Step 5: Run all intelligence use case tests**

```
docker compose exec test_service uv run pytest src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py -v
```

Expected: all PASSED

- [ ] **Step 6: Run full unit test suite to check for regressions**

```
docker compose exec test_service uv run pytest src/tests/unit/ -v --tb=short
```

Expected: all PASSED

- [ ] **Step 7: Commit**

```bash
git add src/modules/intelligence/application/use_cases/analyze_article.py src/tests/unit/modules/intelligence/application/test_analyze_article_use_case.py
git commit -m "$(cat <<'EOF'
🧠 [FEAT] three-tier tag mode logic in AnalyzeArticleUseCase

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Backend schema update

**Files:**
- Modify: `backend/schemas/topic.py`

- [ ] **Step 1: Update `backend/schemas/topic.py`**

```python
from enum import Enum
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class TagMode(str, Enum):
    unsupervised = 'unsupervised'
    semi_supervised = 'semi_supervised'
    supervised = 'supervised'


class TopicCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    tag_mode: TagMode = TagMode.unsupervised


class TopicUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    tag_mode: Optional[TagMode] = None


class TopicOut(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: Optional[str] = None
    color_hex: Optional[str] = None
    prompt_override: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: bool
    tag_mode: TagMode
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Run backend tests**

```
docker compose exec test_service uv run pytest backend/tests/ -v
```

Expected: all PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/schemas/topic.py
git commit -m "$(cat <<'EOF'
🔌 [FEAT] update backend topic schemas for tag_mode enum

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: i18n keys

**Files:**
- Modify: `frontend/lib/providers/locales/en.json`
- Modify: `frontend/lib/providers/locales/zh-TW.json`

- [ ] **Step 1: Add keys to `frontend/lib/providers/locales/en.json`**

Inside the `"tags"` object (after the last existing key `"discardMoves"`), add:

```json
    "tagMode": "Tag Generation Mode",
    "unsupervised": "Unsupervised",
    "unsupervisedDesc": "LLM freely generates all tag groups",
    "semiSupervised": "Semi-supervised",
    "semiSupervisedDesc": "LLM uses existing groups as hints; may add new ones",
    "supervised": "Supervised",
    "supervisedDesc": "LLM is constrained to predefined groups only"
```

- [ ] **Step 2: Add keys to `frontend/lib/providers/locales/zh-TW.json`**

Inside the `"tags"` object (after `"discardMoves"`), add:

```json
    "tagMode": "標籤生成模式",
    "unsupervised": "非監督式",
    "unsupervisedDesc": "LLM 自由生成所有標籤群組",
    "semiSupervised": "半監督式",
    "semiSupervisedDesc": "LLM 參考現有群組，也可新增",
    "supervised": "監督式",
    "supervisedDesc": "LLM 只能使用預定義的標籤群組"
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/providers/locales/en.json frontend/lib/providers/locales/zh-TW.json
git commit -m "$(cat <<'EOF'
🌐 [FEAT] add tag mode i18n keys (en + zh-TW)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: TagModeSelector component + Storybook story

**Files:**
- Create: `frontend/components/features/tags/tag-mode-selector.tsx`
- Create: `frontend/stories/TagModeSelector.stories.tsx`

- [ ] **Step 1: Create `frontend/components/features/tags/tag-mode-selector.tsx`**

```tsx
'use client'

import * as TabsPrimitive from '@radix-ui/react-tabs'
import { TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useI18n } from '@/lib/providers'

export type TagMode = 'unsupervised' | 'semi_supervised' | 'supervised'

interface TagModeSelectorProps {
  value: TagMode
  onChange: (mode: TagMode) => void
  disabled?: boolean
}

export function TagModeSelector({ value, onChange, disabled = false }: TagModeSelectorProps) {
  const { t } = useI18n()
  return (
    <TabsPrimitive.Root value={value} onValueChange={v => onChange(v as TagMode)}>
      <TabsList>
        <TabsTrigger value="unsupervised" disabled={disabled}>
          {t('tags.unsupervised')}
        </TabsTrigger>
        <TabsTrigger value="semi_supervised" disabled={disabled}>
          {t('tags.semiSupervised')}
        </TabsTrigger>
        <TabsTrigger value="supervised" disabled={disabled}>
          {t('tags.supervised')}
        </TabsTrigger>
      </TabsList>
    </TabsPrimitive.Root>
  )
}
```

- [ ] **Step 2: Create `frontend/stories/TagModeSelector.stories.tsx`**

```tsx
import type { Meta, StoryObj } from '@storybook/nextjs-vite'
import React, { useState } from 'react'
import { TagModeSelector, type TagMode } from '../components/features/tags/tag-mode-selector'

const meta: Meta<typeof TagModeSelector> = {
  title: 'Features/Tags/TagModeSelector',
  component: TagModeSelector,
  decorators: [
    (Story) => (
      <div className="p-6">
        <Story />
      </div>
    ),
  ],
  argTypes: {
    value: {
      control: 'select',
      options: ['unsupervised', 'semi_supervised', 'supervised'],
    },
    onChange: { action: 'onChange' },
  },
}
export default meta
type Story = StoryObj<typeof TagModeSelector>

export const Unsupervised: Story = {
  args: {
    value: 'unsupervised',
  },
}

export const SemiSupervised: Story = {
  args: {
    value: 'semi_supervised',
  },
}

export const Supervised: Story = {
  args: {
    value: 'supervised',
  },
}

export const Disabled: Story = {
  args: {
    value: 'unsupervised',
    disabled: true,
  },
}

export const Interactive: Story = {
  render: () => {
    const [mode, setMode] = useState<TagMode>('unsupervised')
    return (
      <div className="space-y-2">
        <TagModeSelector value={mode} onChange={setMode} />
        <p className="text-sm text-muted-foreground">Selected: {mode}</p>
      </div>
    )
  },
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/features/tags/tag-mode-selector.tsx frontend/stories/TagModeSelector.stories.tsx
git commit -m "$(cat <<'EOF'
🎛️ [FEAT] add TagModeSelector segmented control component + story

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Update tags/page.tsx

**Files:**
- Modify: `frontend/app/tags/page.tsx`
- Modify: `frontend/lib/api/topics.ts`

- [ ] **Step 1: Update `frontend/lib/api/topics.ts` — replace `auto_tag_groups`**

In the `Topic` interface, replace:
```typescript
  auto_tag_groups: boolean
```
with:
```typescript
  tag_mode: 'unsupervised' | 'semi_supervised' | 'supervised'
```

- [ ] **Step 2: Update imports in `frontend/app/tags/page.tsx`**

Add `TagModeSelector` and `TagMode` import near the top of the file (with the other feature imports):

```typescript
import { TagModeSelector, type TagMode } from '@/components/features/tags/tag-mode-selector'
```

- [ ] **Step 3: Replace state and handler in `frontend/app/tags/page.tsx`**

Find and replace the `autoTagGroups` state block (approximately lines 418–420):

```typescript
  const [autoTagGroups, setAutoTagGroups] = useState<boolean>(
    selectedTopic?.auto_tag_groups ?? true
  )
```

Replace with:

```typescript
  const [tagMode, setTagMode] = useState<TagMode>(
    (selectedTopic?.tag_mode ?? 'unsupervised') as TagMode
  )
```

Find and replace the sync `useEffect` (approximately lines 449–452):

```typescript
  // Sync autoTagGroups when topic changes
  useEffect(() => {
    setAutoTagGroups(selectedTopic?.auto_tag_groups ?? true)
  }, [selectedTopic?.id])
```

Replace with:

```typescript
  useEffect(() => {
    setTagMode((selectedTopic?.tag_mode ?? 'unsupervised') as TagMode)
  }, [selectedTopic?.id])
```

Find and replace `handleAutoTagGroupsToggle` function (approximately lines 462–470):

```typescript
    setAutoTagGroups(checked)
    try {
      const { updateTopic } = await import('@/lib/api/topics')
      await updateTopic(selectedTopic.id, { auto_tag_groups: checked }, token)
    } catch {
      setAutoTagGroups(!checked)
    }
```

Replace with:

```typescript
  async function handleTagModeChange(mode: TagMode) {
    if (!selectedTopic) return
    const prev = tagMode
    setTagMode(mode)
    try {
      const { updateTopic } = await import('@/lib/api/topics')
      await updateTopic(selectedTopic.id, { tag_mode: mode }, token)
    } catch {
      setTagMode(prev)
    }
  }
```

- [ ] **Step 4: Replace the switch JSX with TagModeSelector (approximately lines 755–765)**

Find:

```tsx
            {selectedTopic && (
              <div className="flex items-center gap-2">
                <Switch
                  id="auto-tag-groups"
                  checked={autoTagGroups}
                  onCheckedChange={handleAutoTagGroupsToggle}
                />
                <label htmlFor="auto-tag-groups" className="text-xs text-muted-foreground cursor-pointer select-none">
                  Auto Tag Groups
                </label>
              </div>
            )}
```

Replace with:

```tsx
            {selectedTopic && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">{t('tags.tagMode')}</span>
                <TagModeSelector value={tagMode} onChange={handleTagModeChange} />
              </div>
            )}
```

- [ ] **Step 5: Remove unused `Switch` import if it's no longer used elsewhere in the file**

Check if `Switch` is used anywhere else in `tags/page.tsx`. If only in the removed block, remove the import line:
```typescript
import { Switch } from '@/components/ui/switch'
```

- [ ] **Step 6: Run frontend type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors related to `auto_tag_groups` or `tag_mode`

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/api/topics.ts frontend/app/tags/page.tsx
git commit -m "$(cat <<'EOF'
🎛️ [FEAT] replace auto_tag_groups switch with TagModeSelector in tags page

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Update admin/topics/page.tsx

**Files:**
- Modify: `frontend/app/admin/topics/page.tsx`

- [ ] **Step 1: Add `TagModeSelector` import**

At the top of `frontend/app/admin/topics/page.tsx`, add:

```typescript
import { TagModeSelector, type TagMode } from '@/components/features/tags/tag-mode-selector'
```

- [ ] **Step 2: Add `tag_mode` to `TopicRow` edit form state**

Find the `form` state initialisation in `TopicRow` (approximately line 41):

```typescript
  const [form, setForm] = useState({
    display_name: topic.display_name,
    description: topic.description ?? '',
    color_hex: topic.color_hex ?? '',
    prompt_override: topic.prompt_override ?? '',
    sort_order: topic.sort_order ?? 0,
    is_active: topic.is_active,
  })
```

Replace with:

```typescript
  const [form, setForm] = useState({
    display_name: topic.display_name,
    description: topic.description ?? '',
    color_hex: topic.color_hex ?? '',
    prompt_override: topic.prompt_override ?? '',
    sort_order: topic.sort_order ?? 0,
    is_active: topic.is_active,
    tag_mode: (topic.tag_mode ?? 'unsupervised') as TagMode,
  })
```

- [ ] **Step 3: Include `tag_mode` in `handleSave` payload**

Find `handleSave` (approximately line 51):

```typescript
    await onUpdate(topic.id, {
      display_name: form.display_name,
      description: form.description || null,
      color_hex: form.color_hex || null,
      prompt_override: form.prompt_override || null,
      sort_order: form.sort_order,
      is_active: form.is_active,
    })
```

Replace with:

```typescript
    await onUpdate(topic.id, {
      display_name: form.display_name,
      description: form.description || null,
      color_hex: form.color_hex || null,
      prompt_override: form.prompt_override || null,
      sort_order: form.sort_order,
      is_active: form.is_active,
      tag_mode: form.tag_mode,
    })
```

- [ ] **Step 4: Add `TagModeSelector` to the `TopicRow` edit form JSX**

Inside the editing form, add after the `sort_order` / `is_active` grid (approximately after line 146), before the Save/Cancel buttons:

```tsx
            <div>
              <label className={labelClass}>{t('tags.tagMode')}</label>
              <TagModeSelector
                value={form.tag_mode}
                onChange={v => setForm(f => ({ ...f, tag_mode: v }))}
              />
            </div>
```

- [ ] **Step 5: Add `tag_mode` to `AddTopicCard` form state**

Find `emptyForm` in `AddTopicCard` (approximately line 237):

```typescript
  const emptyForm = {
    name: '',
    display_name: '',
    description: '',
    color_hex: '',
    prompt_override: '',
    sort_order: 0,
  }
```

Replace with:

```typescript
  const emptyForm = {
    name: '',
    display_name: '',
    description: '',
    color_hex: '',
    prompt_override: '',
    sort_order: 0,
    tag_mode: 'unsupervised' as TagMode,
  }
```

- [ ] **Step 6: Include `tag_mode` in `handleAdd` payload**

Find `handleAdd` (approximately line 247):

```typescript
    await onAdd({
      name: form.name,
      display_name: form.display_name,
      description: form.description || null,
      color_hex: form.color_hex || null,
      prompt_override: form.prompt_override || null,
      sort_order: form.sort_order || null,
    })
```

Replace with:

```typescript
    await onAdd({
      name: form.name,
      display_name: form.display_name,
      description: form.description || null,
      color_hex: form.color_hex || null,
      prompt_override: form.prompt_override || null,
      sort_order: form.sort_order || null,
      tag_mode: form.tag_mode,
    })
```

- [ ] **Step 7: Add `TagModeSelector` to `AddTopicCard` form JSX**

Inside the expanded `AddTopicCard` form, add after the `prompt_override` textarea and before the Create/Cancel buttons:

```tsx
      <div>
        <label className={labelClass}>{t('tags.tagMode')}</label>
        <TagModeSelector
          value={form.tag_mode}
          onChange={v => setForm(f => ({ ...f, tag_mode: v }))}
        />
      </div>
```

- [ ] **Step 8: Update `handleUpdate` type in `TopicsPage` to include `tag_mode`**

The `handleUpdate` function calls `updateTopic(id, data, token)`. The `data` type is `Partial<Topic>` which already includes `tag_mode` from Task 10's `topics.ts` update — no change needed here.

The `handleCreate` function calls `createTopic(data, token)`. Check the `createTopic` signature in `lib/api/topics.ts`:

```typescript
export async function createTopic(
  body: Partial<Pick<Topic, 'name' | 'display_name' | 'color_hex' | 'description' | 'prompt_override' | 'sort_order' | 'is_active'>>,
```

Update to include `tag_mode`:

```typescript
export async function createTopic(
  body: Partial<Pick<Topic, 'name' | 'display_name' | 'color_hex' | 'description' | 'prompt_override' | 'sort_order' | 'is_active' | 'tag_mode'>>,
```

- [ ] **Step 9: Run frontend type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no type errors

- [ ] **Step 10: Run frontend unit tests**

```bash
cd frontend && npm run test
```

Expected: all PASSED

- [ ] **Step 11: Commit**

```bash
git add frontend/app/admin/topics/page.tsx frontend/lib/api/topics.ts
git commit -m "$(cat <<'EOF'
🎛️ [FEAT] add TagModeSelector to admin topics page forms

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] Run the full Python unit test suite one more time:

```
docker compose exec test_service uv run pytest src/tests/unit/ -v --tb=short
```

- [ ] Run the full frontend test suite:

```bash
cd frontend && npm run test
```

- [ ] Verify no remaining references to `auto_tag_groups` in source (excluding migration history):

```bash
grep -r "auto_tag_groups" src/ backend/ frontend/lib frontend/app frontend/components --include="*.py" --include="*.ts" --include="*.tsx"
```

Expected: no matches
