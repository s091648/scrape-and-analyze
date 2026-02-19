# Digital Twins Scraper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Railway-based web scraper that collects Digital Twins articles from RSS feeds, arXiv, and tech blogs, then analyzes them using Claude API.

**Architecture:** Python application running as Railway Cron Jobs. PostgreSQL for storage with SQLAlchemy NullPool. ThreadPoolExecutor for concurrent processing (max 3 workers). Synchronous execution to avoid dual-write problems.

**Tech Stack:** Python 3.11, SQLAlchemy, PostgreSQL, feedparser, BeautifulSoup, Anthropic SDK, structlog, tenacity, pytest

**Drawio Architecture Tracking:** Each phase ends with a drawio task that updates the system architecture diagram using the Write tool (drawio files are XML). Progressive Mermaid diagrams are defined in the [Appendix: Phase Architecture Diagrams](#appendix-phase-architecture-diagrams) section at the bottom of this plan — convert each to drawio XML and write directly to `docs/architecture/digital-twins-scraper.drawio`.

---

## Phase 1: Project Setup

### Task 1.1: Initialize Python project

**Files:**
- Create: `requirements.txt`

**Step 1: Write the file**

```
# requirements.txt
# Core
sqlalchemy>=2.0
psycopg2-binary
beautifulsoup4
requests
feedparser
anthropic
tenacity
structlog
lxml

# Testing
pytest
pytest-cov
responses

# Optional
sentry-sdk
```

**Step 2: Dry-run verify (no execution needed)**

```bash
# Would run: pip install -r requirements.txt --dry-run
# Skip actual execution - file creation is sufficient
```

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "🚀 [FEAT] Initialize Python project with requirements.txt"
```

---

### Task 1.2: Create src/ directory structure

**Files:**
- Create: `src/__init__.py`
- Create: `src/main.py` (empty placeholder)
- Create: `src/config.py` (empty placeholder)
- Create: `src/database.py` (empty placeholder)
- Create: `src/models/__init__.py`
- Create: `src/models/article.py` (empty placeholder)
- Create: `src/models/analysis.py` (empty placeholder)
- Create: `src/models/failed_task.py` (empty placeholder)
- Create: `src/scrapers/__init__.py`
- Create: `src/scrapers/base.py` (empty placeholder)
- Create: `src/scrapers/rss_scraper.py` (empty placeholder)
- Create: `src/scrapers/arxiv_scraper.py` (empty placeholder)
- Create: `src/scrapers/blog_scraper.py` (empty placeholder)
- Create: `src/analyzers/__init__.py`
- Create: `src/analyzers/llm_provider.py` (empty placeholder)
- Create: `src/analyzers/claude.py` (empty placeholder)
- Create: `src/utils/__init__.py`
- Create: `src/utils/sanitizer.py` (empty placeholder)
- Create: `src/utils/logging.py` (empty placeholder)
- Create: `src/prompts/analysis.txt` (empty placeholder)

**Step 1: Create directory structure**

```bash
mkdir -p src/models src/scrapers src/analyzers src/utils src/prompts
touch src/__init__.py src/main.py src/config.py src/database.py
touch src/models/__init__.py src/models/article.py src/models/analysis.py src/models/failed_task.py
touch src/scrapers/__init__.py src/scrapers/base.py src/scrapers/rss_scraper.py src/scrapers/arxiv_scraper.py src/scrapers/blog_scraper.py
touch src/analyzers/__init__.py src/analyzers/llm_provider.py src/analyzers/claude.py
touch src/utils/__init__.py src/utils/sanitizer.py src/utils/logging.py
touch src/prompts/analysis.txt
```

**Step 2: Commit**

```bash
git add src/
git commit -m "📁 [FEAT] Create src/ directory structure"
```

---

### Task 1.3: Create Dockerfile

**Files:**
- Create: `Dockerfile`

**Step 1: Write the file**

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY migrations/ ./migrations/

CMD ["python", "-m", "src.main", "daily"]
```

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "🐳 [FEAT] Add Dockerfile with PYTHONUNBUFFERED=1"
```

---

### Task 1.4: Create railway.toml

**Files:**
- Create: `railway.toml`

**Step 1: Write the file**

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"
```

**Step 2: Commit**

```bash
git add railway.toml
git commit -m "🚂 [FEAT] Add railway.toml for build configuration"
```

---

### Task 1.5: Create .env.example

**Files:**
- Create: `.env.example`

**Step 1: Write the file**

```
DATABASE_URL=postgresql://user:password@localhost:5432/digital_twins
LLM_API_KEY=sk-ant-...
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-20250514
SENTRY_DSN=
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "🔐 [DOCS] Add .env.example with required environment variables"
```

---

### Task 1.6: Set up pytest

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`

**Step 1: Create test directory structure**

```bash
mkdir -p tests/unit tests/integration
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
```

**Step 2: Write pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

**Step 3: Write tests/conftest.py**

```python
import pytest
import os

# Set test environment
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_db')
os.environ.setdefault('LLM_API_KEY', 'test-key')
os.environ.setdefault('LLM_PROVIDER', 'claude')
os.environ.setdefault('LLM_MODEL', 'claude-sonnet-4-20250514')
```

**Step 4: Commit**

```bash
git add tests/ pytest.ini
git commit -m "🧪 [TEST] Set up pytest and test directory structure"
```

---

### Task 1.7: Create docker-compose.yml for local development

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile.dev`

**Step 1: Write Dockerfile.dev**

A development Dockerfile that mirrors the production `Dockerfile` but volume-mounts `src/` for live code changes and installs test dependencies.

```dockerfile
# Dockerfile.dev
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# src/ and migrations/ are volume-mounted, not copied
# This keeps the image identical to production but allows live edits

CMD ["python", "-m", "src.main", "daily"]
```

**Step 2: Write docker-compose.yml**

The `app` service uses the same Python 3.11-slim base and `requirements.txt` as the production Dockerfile deployed on Railway. PostgreSQL 15 mirrors the Railway Postgres plugin. Migrations auto-run via `docker-entrypoint-initdb.d`.

```yaml
# docker-compose.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      - ./src:/app/src
      - ./migrations:/app/migrations
      - ./tests:/app/tests
      - ./pytest.ini:/app/pytest.ini
    environment:
      DATABASE_URL: postgresql://digital_twins:digital_twins@postgres:5432/digital_twins
      LLM_API_KEY: ${LLM_API_KEY:-test-key}
      LLM_PROVIDER: ${LLM_PROVIDER:-claude}
      LLM_MODEL: ${LLM_MODEL:-claude-sonnet-4-20250514}
    depends_on:
      postgres:
        condition: service_healthy
    stdin_open: true
    tty: true

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: digital_twins
      POSTGRES_PASSWORD: digital_twins
      POSTGRES_DB: digital_twins
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U digital_twins"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Step 3: Verify containers start**

```bash
docker compose up -d --build
docker compose ps
```

Expected: Both `app` and `postgres` services are `Up` (healthy).

**Step 4: Verify pytest runs inside container**

```bash
docker compose exec app pytest --co -q
```

Expected: Test collection output (0 tests collected at this stage is fine, no errors).

**Step 5: Commit**

```bash
git add docker-compose.yml Dockerfile.dev
git commit -m "🐳 [FEAT] Add docker-compose.yml for local development mirroring Railway"
```

---

### Task 1.8: Update architecture diagram — Phase 1

**Step 1: Create the architecture directory**

```bash
mkdir -p docs/architecture
```

**Step 2: Render Phase 1 diagram**

Convert the **Phase 1 — Project Setup** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 3: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Add architecture diagram — Phase 1 (Project Setup)"
```

---

## Phase 2: Database Layer

> **For Claude:** From this phase onward, **all commands must run inside the Docker Compose `app` container**. Edit files on the host (they are volume-mounted), but execute tests and scripts via `docker compose exec app <command>`. For example:
> - Run tests: `docker compose exec app pytest tests/unit/test_database.py -v`
> - Run a script: `docker compose exec app python -m src.main daily`
> - Git commits still run on the host.

### Task 2.1: Implement database.py with NullPool

**Files:**
- Modify: `src/database.py`
- Create: `tests/unit/test_database.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_database.py
import pytest
from unittest.mock import patch

def test_engine_uses_nullpool():
    """Engine should use NullPool to avoid connection leaks"""
    with patch.dict('os.environ', {'DATABASE_URL': 'postgresql://test:test@localhost/test'}):
        from src.database import create_engine_with_nullpool
        from sqlalchemy.pool import NullPool

        engine = create_engine_with_nullpool()
        assert isinstance(engine.pool, NullPool)

def test_get_session_returns_session():
    """get_session should return a valid SQLAlchemy session"""
    with patch.dict('os.environ', {'DATABASE_URL': 'postgresql://test:test@localhost/test'}):
        from src.database import get_session
        from sqlalchemy.orm import Session

        session = get_session()
        assert isinstance(session, Session)
        session.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_database.py -v`
Expected: FAIL with "ImportError" or "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

_engine = None
_SessionLocal = None

def create_engine_with_nullpool():
    """Create SQLAlchemy engine with NullPool"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    return create_engine(database_url, poolclass=NullPool)

def get_engine():
    """Get or create the database engine"""
    global _engine
    if _engine is None:
        _engine = create_engine_with_nullpool()
    return _engine

def get_session() -> Session:
    """Get a new database session"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_database.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/database.py tests/unit/test_database.py
git commit -m "🗄️ [FEAT] Implement database.py with SQLAlchemy NullPool"
```

---

### Task 2.2: Create Article model

**Files:**
- Modify: `src/models/article.py`
- Modify: `src/models/__init__.py`
- Create: `tests/unit/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_models.py
import pytest

def test_article_model_has_required_fields():
    """Article model should have all required fields"""
    from src.models.article import Article

    assert hasattr(Article, 'id')
    assert hasattr(Article, 'url')
    assert hasattr(Article, 'url_hash')
    assert hasattr(Article, 'source')
    assert hasattr(Article, 'title')
    assert hasattr(Article, 'content')
    assert hasattr(Article, 'published_at')
    assert hasattr(Article, 'scraped_at')
    assert hasattr(Article, 'metadata_')
    assert hasattr(Article, 'correlation_id')

def test_article_url_is_unique():
    """Article url should have unique constraint"""
    from src.models.article import Article

    url_column = Article.__table__.columns['url']
    assert url_column.unique is True

def test_article_url_hash_has_index():
    """Article url_hash should have an index"""
    from src.models.article import Article

    indexes = {idx.name for idx in Article.__table__.indexes}
    assert any('url_hash' in idx for idx in indexes)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_models.py::test_article_model_has_required_fields -v`
Expected: FAIL with "ImportError"

**Step 3: Write minimal implementation**

```python
# src/models/article.py
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import uuid

Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(Text, unique=True, nullable=False)
    url_hash = Column(String(64), nullable=False)
    source = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True))
    scraped_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    metadata_ = Column('metadata', JSONB)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        Index('idx_articles_url_hash', 'url_hash'),
        Index('idx_articles_source', 'source'),
        Index('idx_articles_scraped_at', 'scraped_at'),
    )
```

```python
# src/models/__init__.py
from src.models.article import Base, Article
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/models/article.py src/models/__init__.py tests/unit/test_models.py
git commit -m "📝 [FEAT] Create Article model with all fields and constraints"
```

---

### Task 2.3: Create Analysis model

**Files:**
- Modify: `src/models/analysis.py`
- Modify: `src/models/__init__.py`
- Modify: `tests/unit/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_models.py (append)

def test_analysis_model_has_required_fields():
    """Analysis model should have all required fields"""
    from src.models.analysis import Analysis

    assert hasattr(Analysis, 'id')
    assert hasattr(Analysis, 'article_id')
    assert hasattr(Analysis, 'correlation_id')
    assert hasattr(Analysis, 'tags')
    assert hasattr(Analysis, 'pain_points')
    assert hasattr(Analysis, 'insights')
    assert hasattr(Analysis, 'innovations')
    assert hasattr(Analysis, 'analyzed_at')
    assert hasattr(Analysis, 'model_used')
    assert hasattr(Analysis, 'input_tokens')
    assert hasattr(Analysis, 'output_tokens')

def test_analysis_has_foreign_key_to_article():
    """Analysis should have foreign key to Article"""
    from src.models.analysis import Analysis

    fk_tables = [fk.column.table.name for fk in Analysis.__table__.foreign_keys]
    assert 'articles' in fk_tables

def test_analysis_article_id_is_unique():
    """Analysis article_id should be unique (one analysis per article)"""
    from src.models.analysis import Analysis

    article_id_column = Analysis.__table__.columns['article_id']
    assert article_id_column.unique is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_models.py::test_analysis_model_has_required_fields -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/models/analysis.py
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from src.models.article import Base

class Analysis(Base):
    __tablename__ = 'analyses'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id'), unique=True, nullable=False)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)
    tags = Column(ARRAY(Text), nullable=False)
    pain_points = Column(Text)
    insights = Column(Text)
    innovations = Column(Text)
    analyzed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    model_used = Column(String(100), nullable=False)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)

    article = relationship("Article", backref="analyses")

    __table_args__ = (
        Index('idx_analyses_article_id', 'article_id'),
        Index('idx_analyses_analyzed_at', 'analyzed_at'),
    )
```

```python
# src/models/__init__.py (update)
from src.models.article import Base, Article
from src.models.analysis import Analysis
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/models/analysis.py src/models/__init__.py tests/unit/test_models.py
git commit -m "📊 [FEAT] Create Analysis model with foreign key to Article"
```

---

### Task 2.4: Create FailedTask model

**Files:**
- Modify: `src/models/failed_task.py`
- Modify: `src/models/__init__.py`
- Modify: `tests/unit/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_models.py (append)

def test_failed_task_model_has_required_fields():
    """FailedTask model should have required fields"""
    from src.models.failed_task import FailedTask

    assert hasattr(FailedTask, 'id')
    assert hasattr(FailedTask, 'task_type')
    assert hasattr(FailedTask, 'article_url')
    assert hasattr(FailedTask, 'article_id')
    assert hasattr(FailedTask, 'exception_type')
    assert hasattr(FailedTask, 'exception_message')
    assert hasattr(FailedTask, 'failed_at')
    assert hasattr(FailedTask, 'resolved')
    assert hasattr(FailedTask, 'resolved_at')

def test_failed_task_has_resolved_index():
    """FailedTask should have index on resolved for efficient queries"""
    from src.models.failed_task import FailedTask

    indexes = {idx.name for idx in FailedTask.__table__.indexes}
    assert any('resolved' in idx for idx in indexes)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_models.py::test_failed_task_model_has_required_fields -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/models/failed_task.py
from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from src.models.article import Base

class FailedTask(Base):
    __tablename__ = 'failed_tasks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(50), nullable=False)  # 'scrape' | 'analyze'
    article_url = Column(Text)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id'))
    exception_type = Column(String(200))
    exception_message = Column(Text)
    failed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index('idx_failed_tasks_resolved', 'resolved'),
        Index('idx_failed_tasks_failed_at', 'failed_at'),
    )
```

```python
# src/models/__init__.py (update)
from src.models.article import Base, Article
from src.models.analysis import Analysis
from src.models.failed_task import FailedTask
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/models/failed_task.py src/models/__init__.py tests/unit/test_models.py
git commit -m "❌ [FEAT] Create FailedTask model for error tracking"
```

---

### Task 2.5: Create database migration scripts

**Files:**
- Create: `migrations/001_initial.sql`

**Step 1: Write the migration file**

```sql
-- migrations/001_initial.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    source VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,
    correlation_id UUID NOT NULL
);

CREATE INDEX idx_articles_url_hash ON articles(url_hash);
CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_scraped_at ON articles(scraped_at);
CREATE INDEX idx_articles_correlation_id ON articles(correlation_id);

CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID UNIQUE NOT NULL REFERENCES articles(id),
    correlation_id UUID NOT NULL,
    tags TEXT[] NOT NULL,
    pain_points TEXT,
    insights TEXT,
    innovations TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    model_used VARCHAR(100) NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER
);

CREATE INDEX idx_analyses_article_id ON analyses(article_id);
CREATE INDEX idx_analyses_analyzed_at ON analyses(analyzed_at);

CREATE TABLE failed_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type VARCHAR(50) NOT NULL,
    article_url TEXT,
    article_id UUID REFERENCES articles(id),
    exception_type VARCHAR(200),
    exception_message TEXT,
    failed_at TIMESTAMPTZ DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_failed_tasks_resolved ON failed_tasks(resolved);
CREATE INDEX idx_failed_tasks_failed_at ON failed_tasks(failed_at);
```

**Step 2: Commit**

```bash
mkdir -p migrations
git add migrations/001_initial.sql
git commit -m "🔄 [FEAT] Add database migration scripts"
```

---

### Task 2.6: Write unit tests for models

This task was completed incrementally in Tasks 2.2-2.4. The tests are already in `tests/unit/test_models.py`.

**Step 1: Commit** (if any additional tests added)

```bash
git add tests/unit/test_models.py
git commit -m "✅ [TEST] Add comprehensive unit tests for models"
```

---

### Task 2.7: Implement helper functions

**Files:**
- Modify: `src/database.py`
- Modify: `tests/unit/test_database.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_database.py (append)

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import uuid

def test_has_analysis_returns_true_when_exists():
    """has_analysis should return True when analysis exists"""
    from src.database import has_analysis

    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()

    result = has_analysis(mock_session, uuid.uuid4())
    assert result is True

def test_has_analysis_returns_false_when_not_exists():
    """has_analysis should return False when no analysis"""
    from src.database import has_analysis

    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = None

    result = has_analysis(mock_session, uuid.uuid4())
    assert result is False

def test_find_recent_failures_filters_by_time():
    """find_recent_failures should filter by time window"""
    from src.database import find_recent_failures

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []

    result = find_recent_failures(mock_session, hours=24)

    # Verify filter was called
    mock_session.query.return_value.filter.assert_called()
    assert result == []

def test_find_missing_analyses_returns_articles_without_analysis():
    """find_missing_analyses should return articles that have no analysis"""
    from src.database import find_missing_analyses

    mock_session = MagicMock()
    mock_article = MagicMock()
    mock_session.query.return_value.outerjoin.return_value.filter.return_value.all.return_value = [mock_article]

    result = find_missing_analyses(mock_session)
    assert len(result) == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_database.py::test_has_analysis_returns_true_when_exists -v`
Expected: FAIL with "ImportError"

**Step 3: Write minimal implementation**

```python
# src/database.py (append to existing file)

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

def has_analysis(session, article_id: UUID) -> bool:
    """Check if article has analysis"""
    from src.models.analysis import Analysis
    return session.query(Analysis).filter_by(article_id=article_id).first() is not None

def find_missing_analyses(session) -> List:
    """Find articles without analysis"""
    from src.models.article import Article
    from src.models.analysis import Analysis
    return session.query(Article).outerjoin(Analysis).filter(Analysis.id == None).all()

def find_recent_failures(session, hours: int = 24) -> List:
    """Find unresolved failures from last N hours"""
    from src.models.failed_task import FailedTask
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return session.query(FailedTask).filter(
        FailedTask.resolved == False,
        FailedTask.failed_at >= cutoff
    ).all()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_database.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/database.py tests/unit/test_database.py
git commit -m "🔍 [FEAT] Implement has_analysis, find_missing_analyses, find_recent_failures"
```

---

### Task 2.8: Update architecture diagram — Phase 2

**Step 1: Create the directory (first time only if Phase 1 diagram was skipped)**

```bash
mkdir -p docs/architecture
```

**Step 2: Render Phase 2 diagram**

Convert the **Phase 2 — Database Layer** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 3: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 2 (Database Layer)"
```

---

## Phase 3: Utilities

### Task 3.1: Implement logging.py with structlog

**Files:**
- Modify: `src/utils/logging.py`
- Create: `tests/unit/test_logging.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_logging.py
import pytest
import json
import sys
from io import StringIO

def test_logger_outputs_json_format(capsys):
    """Logger should output JSON formatted logs"""
    from src.utils.logging import get_logger, configure_logging

    configure_logging()
    logger = get_logger(__name__)
    logger.info("test_event", key="value")

    captured = capsys.readouterr()
    # Parse the JSON output
    log_entry = json.loads(captured.out.strip())
    assert "event" in log_entry
    assert log_entry["key"] == "value"

def test_bind_correlation_id_adds_to_logs(capsys):
    """bind_correlation_id should add correlation_id to all subsequent logs"""
    from src.utils.logging import get_logger, bind_correlation_id, configure_logging

    configure_logging()
    bind_correlation_id("test-corr-123")
    logger = get_logger(__name__)
    logger.info("test_event")

    captured = capsys.readouterr()
    log_entry = json.loads(captured.out.strip())
    assert log_entry.get("correlation_id") == "test-corr-123"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_logging.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/utils/logging.py
import structlog
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')

def bind_correlation_id(correlation_id: str) -> None:
    """Bind correlation_id to current context"""
    correlation_id_var.set(correlation_id)

def get_correlation_id() -> str:
    """Get current correlation_id"""
    return correlation_id_var.get()

def add_correlation_id(logger, method_name, event_dict):
    """Processor to add correlation_id to log events"""
    corr_id = correlation_id_var.get()
    if corr_id:
        event_dict['correlation_id'] = corr_id
    return event_dict

def configure_logging() -> None:
    """Configure structlog for JSON output"""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            add_correlation_id,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

def get_logger(name: str):
    """Get configured structlog logger"""
    return structlog.get_logger(name)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_logging.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/utils/logging.py tests/unit/test_logging.py
git commit -m "📋 [FEAT] Implement structlog JSON logging with correlation_id"
```

---

### Task 3.2: Implement sanitizer.py with sanitize_content()

**Files:**
- Modify: `src/utils/sanitizer.py`
- Create: `tests/unit/test_sanitizer.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_sanitizer.py
import pytest

def test_sanitize_content_removes_script_tags():
    """sanitize_content should remove script tags"""
    from src.utils.sanitizer import sanitize_content

    html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
    result = sanitize_content(html)

    assert "script" not in result.lower()
    assert "alert" not in result
    assert "Hello" in result
    assert "World" in result

def test_sanitize_content_removes_style_tags():
    """sanitize_content should remove style tags"""
    from src.utils.sanitizer import sanitize_content

    html = "<p>Hello</p><style>.hidden{display:none}</style>"
    result = sanitize_content(html)

    assert "style" not in result.lower()
    assert "display" not in result

def test_sanitize_content_removes_nav_footer():
    """sanitize_content should remove nav and footer elements"""
    from src.utils.sanitizer import sanitize_content

    html = "<nav>Navigation</nav><main>Content</main><footer>Footer</footer>"
    result = sanitize_content(html)

    assert "Navigation" not in result
    assert "Footer" not in result
    assert "Content" in result

def test_sanitize_content_preserves_text_with_newlines():
    """sanitize_content should preserve text with paragraph breaks"""
    from src.utils.sanitizer import sanitize_content

    html = "<p>Paragraph 1</p><p>Paragraph 2</p>"
    result = sanitize_content(html)

    assert "Paragraph 1" in result
    assert "Paragraph 2" in result
    assert "\n" in result

def test_sanitize_content_handles_empty_input():
    """sanitize_content should handle empty input"""
    from src.utils.sanitizer import sanitize_content

    assert sanitize_content("") == ""
    assert sanitize_content(None) == ""
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_sanitizer.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/utils/sanitizer.py
from bs4 import BeautifulSoup
from typing import Optional

MAX_CONTENT_LENGTH = 50_000

def sanitize_content(raw_html: Optional[str]) -> str:
    """Convert HTML to plain text and sanitize"""
    if not raw_html:
        return ""

    soup = BeautifulSoup(raw_html, 'html.parser')

    # Remove unwanted tags
    for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
        tag.decompose()

    # Extract text with newlines between elements
    text = soup.get_text(separator='\n', strip=True)

    # Truncate if needed
    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH] + "\n[Content truncated]"

    return text
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_sanitizer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/utils/sanitizer.py tests/unit/test_sanitizer.py
git commit -m "🧹 [FEAT] Implement sanitize_content with HTML removal"
```

---

### Task 3.3: Implement URL hash generation (SHA-256)

**Files:**
- Modify: `src/utils/sanitizer.py`
- Modify: `tests/unit/test_sanitizer.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_sanitizer.py (append)

def test_generate_url_hash_returns_sha256():
    """generate_url_hash should return 64-character SHA-256 hash"""
    from src.utils.sanitizer import generate_url_hash

    url = "https://example.com/article/123"
    result = generate_url_hash(url)

    assert len(result) == 64
    assert result.isalnum()

def test_generate_url_hash_is_deterministic():
    """Same URL should always produce same hash"""
    from src.utils.sanitizer import generate_url_hash

    url = "https://example.com/article/123"
    hash1 = generate_url_hash(url)
    hash2 = generate_url_hash(url)

    assert hash1 == hash2

def test_generate_url_hash_different_for_different_urls():
    """Different URLs should produce different hashes"""
    from src.utils.sanitizer import generate_url_hash

    hash1 = generate_url_hash("https://example.com/1")
    hash2 = generate_url_hash("https://example.com/2")

    assert hash1 != hash2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_sanitizer.py::test_generate_url_hash_returns_sha256 -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/utils/sanitizer.py (append)
import hashlib

def generate_url_hash(url: str) -> str:
    """Generate SHA-256 hash of URL for deduplication"""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_sanitizer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/utils/sanitizer.py tests/unit/test_sanitizer.py
git commit -m "🔐 [FEAT] Implement URL hash generation with SHA-256"
```

---

### Task 3.4: Write unit tests for sanitizer (truncation)

**Files:**
- Modify: `tests/unit/test_sanitizer.py`

**Step 1: Write additional tests**

```python
# tests/unit/test_sanitizer.py (append)

def test_sanitize_content_truncates_long_content():
    """sanitize_content should truncate content exceeding MAX_LENGTH"""
    from src.utils.sanitizer import sanitize_content, MAX_CONTENT_LENGTH

    # Create content longer than max
    long_content = "<p>" + "a" * (MAX_CONTENT_LENGTH + 1000) + "</p>"
    result = sanitize_content(long_content)

    assert len(result) <= MAX_CONTENT_LENGTH + 20  # +20 for truncation message
    assert "[Content truncated]" in result

def test_sanitize_content_does_not_truncate_short_content():
    """sanitize_content should not truncate content under MAX_LENGTH"""
    from src.utils.sanitizer import sanitize_content, MAX_CONTENT_LENGTH

    short_content = "<p>Short content</p>"
    result = sanitize_content(short_content)

    assert "[Content truncated]" not in result
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_sanitizer.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_sanitizer.py
git commit -m "✅ [TEST] Add unit tests for content truncation"
```

---

### Task 3.5: Write unit tests for URL hash generation

**Files:**
- Modify: `tests/unit/test_sanitizer.py`

**Step 1: Add edge case tests**

```python
# tests/unit/test_sanitizer.py (append)

def test_generate_url_hash_handles_unicode():
    """generate_url_hash should handle unicode URLs"""
    from src.utils.sanitizer import generate_url_hash

    url = "https://example.com/文章/数字孪生"
    result = generate_url_hash(url)

    assert len(result) == 64
    assert result.isalnum()

def test_generate_url_hash_handles_special_characters():
    """generate_url_hash should handle special characters in URLs"""
    from src.utils.sanitizer import generate_url_hash

    url = "https://example.com/article?id=123&name=test%20article"
    result = generate_url_hash(url)

    assert len(result) == 64

def test_generate_url_hash_empty_string():
    """generate_url_hash should handle empty string"""
    from src.utils.sanitizer import generate_url_hash

    result = generate_url_hash("")
    assert len(result) == 64  # SHA-256 of empty string
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_sanitizer.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_sanitizer.py
git commit -m "✅ [TEST] Add edge case tests for URL hash generation"
```

---

### Task 3.6: Update architecture diagram — Phase 3

**Step 1: Render Phase 3 diagram**

Convert the **Phase 3 — Utilities** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 3 (Utilities)"
```

---

## Phase 4: RSS Scraper

### Task 4.1: Create BaseScraper abstract class

**Files:**
- Modify: `src/scrapers/base.py`
- Create: `tests/unit/test_scrapers.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_scrapers.py
import pytest

def test_base_scraper_is_abstract():
    """BaseScraper should be abstract and cannot be instantiated"""
    from src.scrapers.base import BaseScraper

    with pytest.raises(TypeError):
        BaseScraper()

def test_base_scraper_requires_scrape_method():
    """Subclass must implement scrape() method"""
    from src.scrapers.base import BaseScraper

    class IncompleteScraper(BaseScraper):
        pass

    with pytest.raises(TypeError):
        IncompleteScraper()

def test_scraped_article_dataclass_has_fields():
    """ScrapedArticle should have required fields"""
    from src.scrapers.base import ScrapedArticle

    article = ScrapedArticle(
        url="https://example.com",
        title="Test",
        content="Content",
        published_at="2024-01-01",
        source="test"
    )

    assert article.url == "https://example.com"
    assert article.title == "Test"
    assert article.source == "test"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_scrapers.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/scrapers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class ScrapedArticle:
    """Data class representing a scraped article"""
    url: str
    title: str
    content: str
    published_at: Optional[str]
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class BaseScraper(ABC):
    """Abstract base class for all scrapers"""

    @abstractmethod
    def scrape(self) -> List[ScrapedArticle]:
        """Scrape and return list of articles"""
        pass
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_scrapers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scrapers/base.py tests/unit/test_scrapers.py
git commit -m "🏗️ [FEAT] Create BaseScraper abstract class and ScrapedArticle dataclass"
```

---

### Task 4.2-4.6: Implement RssScraper class

**Files:**
- Modify: `src/scrapers/rss_scraper.py`
- Create: `tests/unit/test_rss_scraper.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_rss_scraper.py
import pytest
import responses

@responses.activate
def test_rss_scraper_parses_feed():
    """RssScraper should parse RSS feed entries"""
    from src.scrapers.rss_scraper import RssScraper

    rss_content = '''<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Digital Twins in Manufacturing</title>
          <link>https://example.com/digital-twins-article</link>
          <description>An article about digital twins technology.</description>
          <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Unrelated Article</title>
          <link>https://example.com/unrelated</link>
          <description>Nothing about our topic.</description>
          <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>'''

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body=rss_content,
        status=200
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    # Should only get the digital twins article (keyword filtered)
    assert len(articles) == 1
    assert "Digital Twins" in articles[0].title

def test_rss_scraper_matches_keywords():
    """RssScraper should match Digital Twins keywords"""
    from src.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("Digital Twins in Manufacturing") is True
    assert scraper._matches_keywords("The rise of digital twin technology") is True
    assert scraper._matches_keywords("IoT and digital twins") is True
    assert scraper._matches_keywords("Unrelated article about cats") is False

@responses.activate
def test_rss_scraper_handles_network_error():
    """RssScraper should handle network errors gracefully"""
    from src.scrapers.rss_scraper import RssScraper

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body=Exception("Network error")
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []

@responses.activate
def test_rss_scraper_handles_500_error():
    """RssScraper should handle HTTP 500 errors gracefully"""
    from src.scrapers.rss_scraper import RssScraper

    responses.add(
        responses.GET,
        "https://example.com/feed",
        status=500
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_rss_scraper.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/scrapers/rss_scraper.py
import feedparser
import requests
import time
import re
from typing import List
from src.scrapers.base import BaseScraper, ScrapedArticle
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)

DIGITAL_TWINS_KEYWORDS = [
    r'digital\s+twin',
    r'digital\s+twins',
    r'twin\s+technology',
    r'cyber[\-\s]?physical',
    r'virtual\s+replica',
]

class RssScraper(BaseScraper):
    """Scraper for RSS feeds with Digital Twins keyword filtering"""

    def __init__(self, url: str, source: str, rate_limit: float = 1.0):
        self.url = url
        self.source = source
        self.rate_limit = rate_limit
        self._keyword_pattern = re.compile(
            '|'.join(DIGITAL_TWINS_KEYWORDS),
            re.IGNORECASE
        )

    def _matches_keywords(self, text: str) -> bool:
        """Check if text matches Digital Twins keywords"""
        if not text:
            return False
        return bool(self._keyword_pattern.search(text))

    def scrape(self) -> List[ScrapedArticle]:
        """Scrape RSS feed for Digital Twins articles"""
        try:
            response = requests.get(
                self.url,
                timeout=30,
                headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("rss_fetch_failed", url=self.url, error=str(e))
            return []

        feed = feedparser.parse(response.content)
        articles = []

        for entry in feed.entries:
            title = entry.get('title', '')
            description = entry.get('description', '') or entry.get('summary', '')

            # Filter by keywords
            if not self._matches_keywords(title) and not self._matches_keywords(description):
                continue

            content = sanitize_content(description)

            articles.append(ScrapedArticle(
                url=entry.get('link', ''),
                title=title,
                content=content,
                published_at=entry.get('published', ''),
                source=self.source,
                metadata={'author': entry.get('author')}
            ))

            # Rate limiting
            time.sleep(self.rate_limit)

        logger.info("rss_scrape_completed", source=self.source, articles_found=len(articles))
        return articles
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_rss_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scrapers/rss_scraper.py tests/unit/test_rss_scraper.py
git commit -m "📰 [FEAT] Implement RssScraper with feed parsing and keyword filtering"
```

---

### Task 4.7: Configure RSS sources

**Files:**
- Modify: `src/config.py`

**Step 1: Write the configuration**

```python
# src/config.py
import os
from typing import List, Dict, Any

# Environment variables
DATABASE_URL = os.environ.get('DATABASE_URL', '')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'claude')
LLM_MODEL = os.environ.get('LLM_MODEL', 'claude-sonnet-4-20250514')
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')

# RSS Sources (daily)
RSS_SOURCES: List[Dict[str, Any]] = [
    {
        'url': 'https://techcrunch.com/feed/',
        'source': 'techcrunch',
    },
    {
        'url': 'https://venturebeat.com/feed/',
        'source': 'venturebeat',
    },
    {
        'url': 'https://www.iotworldtoday.com/rss.xml',
        'source': 'iotworldtoday',
    },
]

# Blog Sources (weekly)
BLOG_SOURCES: List[Dict[str, Any]] = [
    {
        'base_url': 'https://developer.nvidia.com/blog',
        'source': 'nvidia',
        'selectors': {
            'article_link': 'article a',
            'title': 'h1',
            'content': 'article .content',
        },
    },
    {
        'base_url': 'https://blogs.sw.siemens.com/digital-transformation',
        'source': 'siemens',
        'selectors': {
            'article_link': '.post-title a',
            'title': 'h1.entry-title',
            'content': '.entry-content',
        },
    },
]

def get_sources(schedule_type: str) -> List[Dict[str, Any]]:
    """Get sources based on schedule type"""
    if schedule_type == 'daily':
        return RSS_SOURCES
    elif schedule_type == 'weekly':
        return BLOG_SOURCES
    else:
        return []
```

**Step 2: Commit**

```bash
git add src/config.py
git commit -m "⚙️ [FEAT] Configure RSS and blog sources"
```

---

### Task 4.8: Write unit tests for RSS parsing

**Files:**
- Modify: `tests/unit/test_rss_scraper.py`

**Step 1: Add RSS parsing edge case tests**

```python
# tests/unit/test_rss_scraper.py (append)

@responses.activate
def test_rss_scraper_handles_malformed_xml():
    """RssScraper should handle malformed XML gracefully"""
    from src.scrapers.rss_scraper import RssScraper

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body="<not valid xml",
        status=200
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []

@responses.activate
def test_rss_scraper_handles_empty_feed():
    """RssScraper should handle empty feed"""
    from src.scrapers.rss_scraper import RssScraper

    rss_content = '''<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Empty Feed</title>
      </channel>
    </rss>'''

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body=rss_content,
        status=200
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []

@responses.activate
def test_rss_scraper_extracts_all_fields():
    """RssScraper should extract title, link, description, pubDate"""
    from src.scrapers.rss_scraper import RssScraper

    rss_content = '''<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Digital Twin Innovation</title>
          <link>https://example.com/article</link>
          <description>Content about digital twins</description>
          <pubDate>Tue, 15 Jan 2024 10:00:00 GMT</pubDate>
          <author>John Doe</author>
        </item>
      </channel>
    </rss>'''

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body=rss_content,
        status=200
    )

    scraper = RssScraper(url="https://example.com/feed", source="techcrunch")
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].title == "Digital Twin Innovation"
    assert articles[0].url == "https://example.com/article"
    assert articles[0].source == "techcrunch"
    assert "digital twins" in articles[0].content.lower()
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_rss_scraper.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_rss_scraper.py
git commit -m "✅ [TEST] Add RSS parsing edge case tests"
```

---

### Task 4.9: Write unit tests for keyword filtering

**Files:**
- Modify: `tests/unit/test_rss_scraper.py`

**Step 1: Add keyword filtering tests**

```python
# tests/unit/test_rss_scraper.py (append)

def test_keyword_matching_case_insensitive():
    """Keyword matching should be case insensitive"""
    from src.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("DIGITAL TWINS") is True
    assert scraper._matches_keywords("Digital Twins") is True
    assert scraper._matches_keywords("digital twins") is True

def test_keyword_matching_partial_match():
    """Keyword matching should work with surrounding text"""
    from src.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("The future of digital twins in industry") is True
    assert scraper._matches_keywords("How digital twin technology is evolving") is True

def test_keyword_matching_rejects_unrelated():
    """Keyword matching should reject unrelated content"""
    from src.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("AI and machine learning trends") is False
    assert scraper._matches_keywords("Cloud computing news") is False
    assert scraper._matches_keywords("") is False

def test_keyword_matching_cyber_physical():
    """Keyword matching should match cyber-physical variants"""
    from src.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("cyber-physical systems") is True
    assert scraper._matches_keywords("cyberphysical integration") is True
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_rss_scraper.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_rss_scraper.py
git commit -m "✅ [TEST] Add keyword filtering unit tests"
```

---

### Task 4.10: Update architecture diagram — Phase 4

**Step 1: Render Phase 4 diagram**

Convert the **Phase 4 — RSS Scraper** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 4 (RSS Scraper)"
```

---

## Phase 5: arXiv API Scraper

### Task 5.1-5.5: Implement ArxivScraper

**Files:**
- Modify: `src/scrapers/arxiv_scraper.py`
- Create: `tests/unit/test_arxiv_scraper.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_arxiv_scraper.py
import pytest
import responses
from datetime import datetime, timedelta

def test_arxiv_scraper_builds_query():
    """ArxivScraper should build correct search query"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper()
    query = scraper._build_query()

    assert "digital" in query.lower() or "twin" in query.lower()

@responses.activate
def test_arxiv_scraper_parses_atom_response():
    """ArxivScraper should parse Atom XML response"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    atom_response = '''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Digital Twins for Smart Manufacturing</title>
        <summary>This paper presents a framework for digital twins...</summary>
        <published>2024-01-15T00:00:00Z</published>
        <author><name>John Doe</name></author>
        <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
      </entry>
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper(max_results=10)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert "Digital Twins" in articles[0].title
    assert articles[0].source == "arxiv"

def test_arxiv_scraper_respects_max_results():
    """ArxivScraper should respect max_results limit"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper(max_results=50)
    assert scraper.max_results == 50

    scraper_default = ArxivScraper()
    assert scraper_default.max_results == 100

@responses.activate
def test_arxiv_scraper_handles_empty_response():
    """ArxivScraper should handle empty response gracefully"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    atom_response = '''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert articles == []

@responses.activate
def test_arxiv_scraper_handles_api_error():
    """ArxivScraper should handle API errors gracefully"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        status=500
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert articles == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_arxiv_scraper.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/scrapers/arxiv_scraper.py
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import List
from urllib.parse import urlencode
from src.scrapers.base import BaseScraper, ScrapedArticle
from src.utils.logging import get_logger

logger = get_logger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"

class ArxivScraper(BaseScraper):
    """Scraper for arXiv API"""

    def __init__(self, max_results: int = 100, days_back: int = 7):
        self.max_results = max_results
        self.days_back = days_back

    def _build_query(self) -> str:
        """Build arXiv search query for Digital Twins"""
        # Search in title and abstract
        terms = [
            'ti:"digital twin"',
            'ti:"digital twins"',
            'abs:"digital twin"',
            'abs:"cyber-physical"',
        ]
        return ' OR '.join(terms)

    def scrape(self) -> List[ScrapedArticle]:
        """Scrape arXiv API for Digital Twins papers"""
        query = self._build_query()

        params = {
            'search_query': query,
            'start': 0,
            'max_results': self.max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending',
        }

        try:
            response = requests.get(
                ARXIV_API_URL,
                params=params,
                timeout=60,
                headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("arxiv_fetch_failed", error=str(e))
            return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error("arxiv_parse_failed", error=str(e))
            return []

        articles = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.days_back)

        for entry in root.findall(f'{ATOM_NS}entry'):
            # Extract data
            title_elem = entry.find(f'{ATOM_NS}title')
            summary_elem = entry.find(f'{ATOM_NS}summary')
            published_elem = entry.find(f'{ATOM_NS}published')
            id_elem = entry.find(f'{ATOM_NS}id')

            title = title_elem.text.strip() if title_elem is not None else ''
            summary = summary_elem.text.strip() if summary_elem is not None else ''
            published = published_elem.text if published_elem is not None else ''
            arxiv_id = id_elem.text if id_elem is not None else ''

            # Extract authors
            authors = []
            for author in entry.findall(f'{ATOM_NS}author'):
                name_elem = author.find(f'{ATOM_NS}name')
                if name_elem is not None:
                    authors.append(name_elem.text)

            # Get link
            link = ''
            for link_elem in entry.findall(f'{ATOM_NS}link'):
                if link_elem.get('rel') == 'alternate':
                    link = link_elem.get('href', '')
                    break

            if not link:
                link = arxiv_id

            # Filter by date
            try:
                pub_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
                if pub_date < cutoff_date:
                    continue
            except (ValueError, AttributeError):
                pass

            articles.append(ScrapedArticle(
                url=link,
                title=title,
                content=summary,
                published_at=published,
                source='arxiv',
                metadata={'authors': authors, 'arxiv_id': arxiv_id}
            ))

        logger.info("arxiv_scrape_completed", articles_found=len(articles))
        return articles
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_arxiv_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scrapers/arxiv_scraper.py tests/unit/test_arxiv_scraper.py
git commit -m "📚 [FEAT] Implement ArxivScraper with API query and date filtering"
```

---

### Task 5.6: Write unit tests for arXiv API response parsing

**Files:**
- Modify: `tests/unit/test_arxiv_scraper.py`

**Step 1: Add comprehensive arXiv API tests**

```python
# tests/unit/test_arxiv_scraper.py (append)

@responses.activate
def test_arxiv_scraper_extracts_authors():
    """ArxivScraper should extract multiple authors"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    atom_response = '''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Digital Twins Research</title>
        <summary>Abstract text</summary>
        <published>2024-01-15T00:00:00Z</published>
        <author><name>John Doe</name></author>
        <author><name>Jane Smith</name></author>
        <author><name>Bob Johnson</name></author>
        <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
      </entry>
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].metadata['authors'] == ['John Doe', 'Jane Smith', 'Bob Johnson']

@responses.activate
def test_arxiv_scraper_filters_old_papers():
    """ArxivScraper should filter papers older than days_back"""
    from src.scrapers.arxiv_scraper import ArxivScraper
    from datetime import datetime, timedelta, timezone

    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    atom_response = f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Old Paper</title>
        <summary>Abstract</summary>
        <published>{old_date}</published>
        <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate"/>
      </entry>
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper(days_back=7)
    articles = scraper.scrape()

    assert len(articles) == 0  # Should be filtered out

@responses.activate
def test_arxiv_scraper_handles_missing_fields():
    """ArxivScraper should handle entries with missing optional fields"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    atom_response = '''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Minimal Entry</title>
        <summary></summary>
        <published>2024-01-15T00:00:00Z</published>
      </entry>
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].title == "Minimal Entry"
    assert articles[0].content == ""
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_arxiv_scraper.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_arxiv_scraper.py
git commit -m "✅ [TEST] Add comprehensive arXiv API parsing tests"
```

---

### Task 5.7: Update architecture diagram — Phase 5

**Step 1: Render Phase 5 diagram**

Convert the **Phase 5 — arXiv Scraper** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 5 (arXiv Scraper)"
```

---

## Phase 6: Blog Scraper

### Task 6.1-6.5: Implement BlogScraper

**Files:**
- Modify: `src/scrapers/blog_scraper.py`
- Create: `tests/unit/test_blog_scraper.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_blog_scraper.py
import pytest
import responses
from urllib.robotparser import RobotFileParser

def test_blog_scraper_extracts_article_links():
    """BlogScraper should extract article links from listing page"""
    from src.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <article>
          <a href="/blog/digital-twins-article">Article 1</a>
        </article>
        <article>
          <a href="/blog/another-article">Article 2</a>
        </article>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com/blog",
        source="test",
        selectors={'article_link': 'article a', 'title': 'h1', 'content': '.content'}
    )

    links = scraper._extract_links(html)
    assert len(links) == 2
    assert "/blog/digital-twins-article" in links[0]

def test_blog_scraper_extracts_content():
    """BlogScraper should extract title and content with selectors"""
    from src.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <h1>Article Title</h1>
        <div class="content">
          <p>This is the article content about digital twins.</p>
        </div>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    title, content = scraper._extract_article(html)
    assert title == "Article Title"
    assert "digital twins" in content

@responses.activate
def test_blog_scraper_checks_robots_txt():
    """BlogScraper should check robots.txt before scraping"""
    from src.scrapers.blog_scraper import BlogScraper

    robots_content = """
    User-agent: *
    Disallow: /private/
    Allow: /blog/
    """

    responses.add(
        responses.GET,
        "https://example.com/robots.txt",
        body=robots_content,
        status=200
    )

    scraper = BlogScraper(
        base_url="https://example.com/blog",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    assert scraper._can_fetch("https://example.com/blog/article") is True
    assert scraper._can_fetch("https://example.com/private/data") is False

@responses.activate
def test_blog_scraper_handles_missing_robots_txt():
    """BlogScraper should allow scraping when robots.txt is missing"""
    from src.scrapers.blog_scraper import BlogScraper

    responses.add(
        responses.GET,
        "https://example.com/robots.txt",
        status=404
    )

    scraper = BlogScraper(
        base_url="https://example.com/blog",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    # Should allow scraping when robots.txt is missing
    assert scraper._can_fetch("https://example.com/blog/article") is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_blog_scraper.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/scrapers/blog_scraper.py
import requests
import time
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from src.scrapers.base import BaseScraper, ScrapedArticle
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)

class BlogScraper(BaseScraper):
    """Scraper for blog websites with CSS selectors"""

    def __init__(
        self,
        base_url: str,
        source: str,
        selectors: Dict[str, str],
        rate_limit: float = 2.0
    ):
        self.base_url = base_url
        self.source = source
        self.selectors = selectors
        self.rate_limit = rate_limit
        self._robot_parser: Optional[RobotFileParser] = None

    def _get_robot_parser(self) -> RobotFileParser:
        """Get or create robot parser"""
        if self._robot_parser is None:
            self._robot_parser = RobotFileParser()
            parsed = urlparse(self.base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            try:
                self._robot_parser.set_url(robots_url)
                self._robot_parser.read()
            except Exception as e:
                logger.warning("robots_txt_fetch_failed", url=robots_url, error=str(e))
        return self._robot_parser

    def _can_fetch(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        parser = self._get_robot_parser()
        try:
            return parser.can_fetch("Digital-Twins-Scraper", url)
        except Exception:
            # Allow if we can't determine
            return True

    def _extract_links(self, html: str) -> List[str]:
        """Extract article links from listing page"""
        soup = BeautifulSoup(html, 'html.parser')
        selector = self.selectors.get('article_link', 'a')
        links = []

        for link in soup.select(selector):
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                links.append(full_url)

        return links

    def _extract_article(self, html: str) -> Tuple[str, str]:
        """Extract title and content from article page"""
        soup = BeautifulSoup(html, 'html.parser')

        title_selector = self.selectors.get('title', 'h1')
        content_selector = self.selectors.get('content', 'article')

        title_elem = soup.select_one(title_selector)
        title = title_elem.get_text(strip=True) if title_elem else ''

        content_elem = soup.select_one(content_selector)
        content = sanitize_content(str(content_elem)) if content_elem else ''

        return title, content

    def _matches_keywords(self, text: str) -> bool:
        """Check if text matches Digital Twins keywords"""
        keywords = ['digital twin', 'digital twins', 'cyber-physical', 'virtual replica']
        text_lower = text.lower()
        return any(kw in text_lower for kw in keywords)

    def scrape(self) -> List[ScrapedArticle]:
        """Scrape blog for Digital Twins articles"""
        articles = []

        # Fetch listing page
        try:
            response = requests.get(
                self.base_url,
                timeout=30,
                headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("blog_listing_fetch_failed", url=self.base_url, error=str(e))
            return []

        links = self._extract_links(response.text)
        logger.info("blog_links_discovered", source=self.source, count=len(links))

        for link in links[:20]:  # Limit to prevent excessive scraping
            if not self._can_fetch(link):
                logger.info("blog_url_blocked_by_robots", url=link)
                continue

            time.sleep(self.rate_limit)

            try:
                article_response = requests.get(
                    link,
                    timeout=30,
                    headers={'User-Agent': 'Digital-Twins-Scraper/1.0'}
                )
                article_response.raise_for_status()
            except Exception as e:
                logger.warning("blog_article_fetch_failed", url=link, error=str(e))
                continue

            title, content = self._extract_article(article_response.text)

            # Filter by keywords
            if not self._matches_keywords(title) and not self._matches_keywords(content):
                continue

            articles.append(ScrapedArticle(
                url=link,
                title=title,
                content=content,
                published_at=None,
                source=self.source,
            ))

        logger.info("blog_scrape_completed", source=self.source, articles_found=len(articles))
        return articles
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_blog_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scrapers/blog_scraper.py tests/unit/test_blog_scraper.py
git commit -m "📝 [FEAT] Implement BlogScraper with CSS selectors and robots.txt checking"
```

---

### Task 6.6: Configure blog sources (NVIDIA, Siemens, AWS IoT, Azure IoT)

**Files:**
- Modify: `src/config.py`

**Step 1: Update BLOG_SOURCES with complete configurations**

```python
# src/config.py (update BLOG_SOURCES)

BLOG_SOURCES: List[Dict[str, Any]] = [
    {
        'base_url': 'https://developer.nvidia.com/blog',
        'source': 'nvidia',
        'selectors': {
            'article_link': '.post-card a.post-card__link',
            'title': 'h1.post-title',
            'content': '.post-content',
        },
    },
    {
        'base_url': 'https://blogs.sw.siemens.com/digital-transformation',
        'source': 'siemens',
        'selectors': {
            'article_link': 'article.post a.entry-title-link',
            'title': 'h1.entry-title',
            'content': '.entry-content',
        },
    },
    {
        'base_url': 'https://aws.amazon.com/blogs/iot',
        'source': 'aws_iot',
        'selectors': {
            'article_link': '.blog-post a.title',
            'title': 'h1.blog-post-title',
            'content': '.blog-post-content',
        },
    },
    {
        'base_url': 'https://azure.microsoft.com/en-us/blog/topics/internet-of-things',
        'source': 'azure_iot',
        'selectors': {
            'article_link': '.card a.card-link',
            'title': 'h1.article-title',
            'content': '.article-content',
        },
    },
]
```

**Step 2: Commit**

```bash
git add src/config.py
git commit -m "⚙️ [FEAT] Configure blog sources (NVIDIA, Siemens, AWS IoT, Azure IoT)"
```

---

### Task 6.7: Write unit tests for blog parsing with mock HTML

**Files:**
- Modify: `tests/unit/test_blog_scraper.py`

**Step 1: Add comprehensive blog parsing tests**

```python
# tests/unit/test_blog_scraper.py (append)

def test_blog_scraper_removes_nav_footer_from_content():
    """BlogScraper should exclude nav and footer from extracted content"""
    from src.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <nav>Navigation Menu</nav>
        <article>
          <h1>Article Title</h1>
          <div class="content">
            <p>Main content about digital twins.</p>
          </div>
        </article>
        <footer>Copyright 2024</footer>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    title, content = scraper._extract_article(html)
    assert "Navigation" not in content
    assert "Copyright" not in content
    assert "digital twins" in content

def test_blog_scraper_handles_missing_content():
    """BlogScraper should handle pages with missing content selector"""
    from src.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <h1>Title Only</h1>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.nonexistent'}
    )

    title, content = scraper._extract_article(html)
    assert title == "Title Only"
    assert content == ""

def test_blog_scraper_converts_relative_links():
    """BlogScraper should convert relative links to absolute URLs"""
    from src.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <a href="/blog/article-1">Article 1</a>
        <a href="article-2">Article 2</a>
        <a href="https://other.com/article">External</a>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com/blog",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    links = scraper._extract_links(html)
    assert "https://example.com/blog/article-1" in links
    assert "https://example.com/blog/article-2" in links
    assert "https://other.com/article" in links

@responses.activate
def test_blog_scraper_respects_rate_limit():
    """BlogScraper should wait between requests"""
    from src.scrapers.blog_scraper import BlogScraper
    from unittest.mock import patch
    import time

    listing_html = '<html><a href="/article">Link</a></html>'
    article_html = '<html><h1>Digital Twin</h1><div class="content">Content</div></html>'

    responses.add(responses.GET, "https://example.com/blog", body=listing_html, status=200)
    responses.add(responses.GET, "https://example.com/article", body=article_html, status=200)
    responses.add(responses.GET, "https://example.com/robots.txt", status=404)

    with patch('time.sleep') as mock_sleep:
        scraper = BlogScraper(
            base_url="https://example.com/blog",
            source="test",
            selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'},
            rate_limit=2.0
        )
        scraper.scrape()

        # Should have called sleep with rate_limit value
        mock_sleep.assert_called_with(2.0)
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_blog_scraper.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_blog_scraper.py
git commit -m "✅ [TEST] Add comprehensive blog parsing tests with mock HTML"
```

---

### Task 6.8: Update architecture diagram — Phase 6

**Step 1: Render Phase 6 diagram**

Convert the **Phase 6 — Complete Scraper Layer** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 6 (Complete Scraper Layer)"
```

---

## Phase 7: LLM Analyzer

### Task 7.1-7.2: Create LLMProvider and AnalysisResult

**Files:**
- Modify: `src/analyzers/llm_provider.py`
- Create: `tests/unit/test_llm_provider.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_llm_provider.py
import pytest

def test_llm_provider_is_abstract():
    """LLMProvider should be abstract"""
    from src.analyzers.llm_provider import LLMProvider

    with pytest.raises(TypeError):
        LLMProvider()

def test_llm_provider_requires_analyze_method():
    """Subclass must implement analyze() method"""
    from src.analyzers.llm_provider import LLMProvider

    class IncompleteProvider(LLMProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()

def test_analysis_result_has_all_fields():
    """AnalysisResult should have all required fields"""
    from src.analyzers.llm_provider import AnalysisResult

    result = AnalysisResult(
        tags=["tag1", "tag2"],
        pain_points="Some pain points",
        insights="Key insights",
        innovations="New innovations",
        input_tokens=100,
        output_tokens=50
    )

    assert result.tags == ["tag1", "tag2"]
    assert result.pain_points == "Some pain points"
    assert result.insights == "Key insights"
    assert result.innovations == "New innovations"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_llm_provider.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/analyzers/llm_provider.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class AnalysisResult:
    """Result from LLM analysis"""
    tags: List[str]
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

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_llm_provider.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/analyzers/llm_provider.py tests/unit/test_llm_provider.py
git commit -m "🤖 [FEAT] Create LLMProvider abstract class and AnalysisResult dataclass"
```

---

### Task 7.3-7.7: Implement ClaudeProvider

**Files:**
- Modify: `src/analyzers/claude.py`
- Create: `tests/unit/test_claude_provider.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_claude_provider.py
import pytest
from unittest.mock import Mock, patch, MagicMock

def test_claude_provider_inherits_from_llm_provider():
    """ClaudeProvider should inherit from LLMProvider"""
    from src.analyzers.claude import ClaudeProvider
    from src.analyzers.llm_provider import LLMProvider

    assert issubclass(ClaudeProvider, LLMProvider)

def test_claude_provider_calls_anthropic_api():
    """ClaudeProvider should call Anthropic API"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        # Setup mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":["digital twin"],"pain_points":"none","insights":"test","innovations":"new"}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test content", "analyze this")

        assert result is not None
        assert result.tags == ["digital twin"]
        assert result.input_tokens == 100
        assert result.output_tokens == 50

def test_claude_provider_retries_on_transient_error():
    """ClaudeProvider should retry on transient errors"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":[],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_anthropic.Anthropic.return_value.messages.create.side_effect = [
            Exception("Temporary error"),
            mock_response
        ]

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        # Should have retried
        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 2
        assert result is not None

def test_claude_provider_handles_invalid_json():
    """ClaudeProvider should handle invalid JSON response"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='not valid json')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        # Should return None on invalid JSON
        assert result is None

def test_claude_provider_tracks_token_usage():
    """ClaudeProvider should track input and output tokens"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":["test"],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test content", "analyze")

        assert result.input_tokens == 500
        assert result.output_tokens == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_claude_provider.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/analyzers/claude.py
import anthropic
import json
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.analyzers.llm_provider import LLMProvider, AnalysisResult
from src.utils.logging import get_logger

logger = get_logger(__name__)

class ClaudeProvider(LLMProvider):
    """LLM Provider using Anthropic's Claude API"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((anthropic.APIError, anthropic.APIConnectionError))
    )
    def _call_api(self, content: str, prompt: str):
        """Call Claude API with retry logic"""
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"

        return self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": full_prompt}]
        )

    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        """Analyze content using Claude API"""
        try:
            response = self._call_api(content, prompt)
        except Exception as e:
            logger.error("claude_api_call_failed", error=str(e))
            return None

        # Parse response
        try:
            response_text = response.content[0].text
            result_json = json.loads(response_text)
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.error("claude_response_parse_failed", error=str(e))
            return None

        # Validate required fields
        required_fields = ['tags', 'pain_points', 'insights', 'innovations']
        if not all(field in result_json for field in required_fields):
            logger.error("claude_response_missing_fields", fields=list(result_json.keys()))
            return None

        return AnalysisResult(
            tags=result_json.get('tags', []),
            pain_points=result_json.get('pain_points', ''),
            insights=result_json.get('insights', ''),
            innovations=result_json.get('innovations', ''),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_claude_provider.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/analyzers/claude.py tests/unit/test_claude_provider.py
git commit -m "🧠 [FEAT] Implement ClaudeProvider with retry logic and token tracking"
```

---

### Task 7.4: Create analysis prompt template

**Files:**
- Modify: `src/prompts/analysis.txt`

**Step 1: Write the prompt template**

```
You are a professional technology analyst specializing in Digital Twins, IoT, and Industry 4.0.

Analyze the following article and extract structured insights. Focus on:

1. **tags**: 3-7 relevant keywords or topics (e.g., "digital twin", "manufacturing", "predictive maintenance")
2. **pain_points**: Key challenges, problems, or barriers mentioned in the article
3. **insights**: Important observations, trends, or takeaways
4. **innovations**: New technologies, methods, solutions, or approaches mentioned

Return your analysis as valid JSON with these exact fields:
{
  "tags": ["tag1", "tag2", "tag3"],
  "pain_points": "Description of challenges mentioned...",
  "insights": "Key observations and trends...",
  "innovations": "New technologies or approaches..."
}

IMPORTANT: Output ONLY the JSON object, no other text or explanation.
```

**Step 2: Commit**

```bash
git add src/prompts/analysis.txt
git commit -m "📄 [FEAT] Create analysis prompt template"
```

---

### Task 7.5: Implement JSON response parsing and validation

**Files:**
- Modify: `src/analyzers/claude.py`
- Modify: `tests/unit/test_claude_provider.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_claude_provider.py (append)

def test_claude_provider_validates_required_fields():
    """ClaudeProvider should validate all required fields are present"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        # Response missing 'innovations' field
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":["test"],"pain_points":"","insights":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is None  # Should fail validation

def test_claude_provider_validates_tags_is_array():
    """ClaudeProvider should validate that tags is an array"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        # Response with tags as string instead of array
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":"not-an-array","pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is None  # Should fail validation
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_claude_provider.py::test_claude_provider_validates_required_fields -v`
Expected: FAIL (if validation not yet implemented)

**Step 3: Update implementation to validate**

```python
# src/analyzers/claude.py (update analyze method)

def _validate_response(self, result_json: dict) -> bool:
    """Validate LLM response has required fields with correct types"""
    required_fields = ['tags', 'pain_points', 'insights', 'innovations']

    # Check all required fields exist
    if not all(field in result_json for field in required_fields):
        logger.error("claude_response_missing_fields",
                     expected=required_fields,
                     actual=list(result_json.keys()))
        return False

    # Validate tags is a list
    if not isinstance(result_json.get('tags'), list):
        logger.error("claude_response_invalid_tags", tags_type=type(result_json.get('tags')).__name__)
        return False

    return True
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_claude_provider.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/analyzers/claude.py tests/unit/test_claude_provider.py
git commit -m "✅ [FEAT] Implement JSON response validation for LLM output"
```

---

### Task 7.6: Implement token usage tracking

**Files:**
- Modify: `src/analyzers/claude.py`
- Modify: `tests/unit/test_claude_provider.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_claude_provider.py (append)

def test_claude_provider_logs_token_metrics():
    """ClaudeProvider should log token usage metrics"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        with patch('src.analyzers.claude.logger') as mock_logger:
            from src.analyzers.claude import ClaudeProvider

            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"tags":[],"pain_points":"","insights":"","innovations":""}')]
            mock_response.usage.input_tokens = 1500
            mock_response.usage.output_tokens = 300
            mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

            provider = ClaudeProvider(api_key="test-key")
            result = provider.analyze("test content", "analyze")

            # Verify logging was called with token metrics
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args
            assert 'input_tokens' in str(call_args) or result.input_tokens == 1500
```

**Step 2: Update implementation**

```python
# src/analyzers/claude.py (add logging in analyze method, before return)

logger.info("llm_analysis_completed",
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens)
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/unit/test_claude_provider.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/analyzers/claude.py tests/unit/test_claude_provider.py
git commit -m "📊 [FEAT] Implement token usage tracking and logging"
```

---

### Task 7.7: Implement retry logic with tenacity

**Files:**
- Modify: `tests/unit/test_claude_provider.py`

**Step 1: Write comprehensive retry tests**

```python
# tests/unit/test_claude_provider.py (append)

def test_claude_provider_retries_on_rate_limit():
    """ClaudeProvider should retry on 429 rate limit error"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider
        import anthropic

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":[],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        # First two calls raise rate limit, third succeeds
        rate_limit_error = anthropic.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body={}
        )
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            mock_response
        ]

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is not None
        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 3

def test_claude_provider_gives_up_after_max_retries():
    """ClaudeProvider should give up after 3 retries"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider
        import anthropic

        api_error = anthropic.APIError(
            message="Server error",
            request=MagicMock(),
            body={}
        )
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = api_error

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert result is None
        assert mock_anthropic.Anthropic.return_value.messages.create.call_count == 3
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_claude_provider.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_claude_provider.py
git commit -m "✅ [TEST] Add retry logic tests for rate limiting and API errors"
```

---

### Task 7.8: Write unit tests with mocked LLM responses

**Files:**
- Modify: `tests/unit/test_claude_provider.py`

**Step 1: Add edge case tests**

```python
# tests/unit/test_claude_provider.py (append)

def test_claude_provider_handles_empty_content():
    """ClaudeProvider should handle empty article content"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":["empty"],"pain_points":"","insights":"No content","innovations":""}')]
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 30
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("", "analyze this empty content")

        assert result is not None

def test_claude_provider_handles_unicode_content():
    """ClaudeProvider should handle unicode content"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":["数字孪生","デジタルツイン"],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 100
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("数字孪生技術の記事", "analyze")

        assert result is not None
        assert "数字孪生" in result.tags

def test_claude_provider_handles_large_content():
    """ClaudeProvider should handle large content without error"""
    with patch('src.analyzers.claude.anthropic') as mock_anthropic:
        from src.analyzers.claude import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"tags":["test"],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 50000
        mock_response.usage.output_tokens = 500
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        large_content = "Digital twins content. " * 5000  # ~100KB of text
        result = provider.analyze(large_content, "analyze")

        assert result is not None
        assert result.input_tokens == 50000
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_claude_provider.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_claude_provider.py
git commit -m "✅ [TEST] Add edge case tests for LLM with mocked responses"
```

---

### Task 7.9: Update architecture diagram — Phase 7

**Step 1: Render Phase 7 diagram**

Convert the **Phase 7 — LLM Analyzer** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 7 (LLM Analyzer)"
```

---

## Phase 8: Main Execution Flow

### Task 8.1: Implement CLI entry point

**Files:**
- Modify: `src/main.py`
- Create: `tests/unit/test_main.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_main.py
import pytest
from unittest.mock import patch, MagicMock

def test_parse_args_accepts_daily():
    """parse_args should accept 'daily' command"""
    from src.main import parse_args

    args = parse_args(['daily'])
    assert args.command == 'daily'

def test_parse_args_accepts_weekly():
    """parse_args should accept 'weekly' command"""
    from src.main import parse_args

    args = parse_args(['weekly'])
    assert args.command == 'weekly'

def test_parse_args_accepts_remediate():
    """parse_args should accept 'remediate' command"""
    from src.main import parse_args

    args = parse_args(['remediate'])
    assert args.command == 'remediate'

def test_parse_args_rejects_invalid_command():
    """parse_args should reject invalid commands"""
    from src.main import parse_args

    with pytest.raises(SystemExit):
        parse_args(['invalid'])
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/main.py
import argparse
import uuid
import time
import signal
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from src.utils.logging import get_logger, bind_correlation_id, configure_logging
from src.config import get_sources, LLM_API_KEY, LLM_MODEL, DATABASE_URL
from src.database import get_session, has_analysis, find_recent_failures

logger = get_logger(__name__)

MAX_WORKERS = 3
MAX_EXECUTION_TIME = 50 * 60  # 50 minutes
BATCH_SIZE = 50

# Global flag for graceful shutdown
_shutdown_requested = False

def parse_args(args=None):
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Digital Twins Scraper')
    parser.add_argument('command', choices=['daily', 'weekly', 'remediate'],
                        help='Execution mode: daily, weekly, or remediate')
    return parser.parse_args(args)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global _shutdown_requested
    logger.warning("shutdown_signal_received", signal=signum)
    _shutdown_requested = True

def main():
    """Main entry point"""
    # Configure logging first
    configure_logging()

    # Parse arguments
    args = parse_args()

    # Generate correlation ID
    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("execution_started", command=args.command, correlation_id=correlation_id)

    start_time = time.time()

    try:
        if args.command == 'daily':
            run_daily_scrape(start_time)
        elif args.command == 'weekly':
            run_weekly_scrape(start_time)
        elif args.command == 'remediate':
            run_remediate()
    except Exception as e:
        logger.error("execution_failed", error=str(e))
        raise
    finally:
        duration = time.time() - start_time
        logger.info("execution_completed", duration_seconds=duration)

if __name__ == '__main__':
    main()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/main.py tests/unit/test_main.py
git commit -m "🚀 [FEAT] Implement CLI entry point with argparse"
```

---

### Task 8.2-8.10: Implement execution functions

**Files:**
- Modify: `src/main.py`
- Modify: `tests/unit/test_main.py`

**Step 1: Write additional tests**

```python
# tests/unit/test_main.py (append)

def test_check_timeout_returns_true_when_exceeded():
    """check_timeout should return True when max time exceeded"""
    from src.main import check_timeout, MAX_EXECUTION_TIME
    import time

    # Start time in the past
    start_time = time.time() - MAX_EXECUTION_TIME - 1
    assert check_timeout(start_time) is True

def test_check_timeout_returns_false_when_not_exceeded():
    """check_timeout should return False when within time limit"""
    from src.main import check_timeout
    import time

    start_time = time.time()
    assert check_timeout(start_time) is False

@patch('src.main.get_session')
@patch('src.main.RssScraper')
def test_run_daily_scrape_uses_rss_sources(mock_rss_scraper, mock_get_session):
    """run_daily_scrape should use RSS sources"""
    from src.main import run_daily_scrape
    import time

    mock_session = MagicMock()
    mock_get_session.return_value = mock_session
    mock_scraper_instance = MagicMock()
    mock_scraper_instance.scrape.return_value = []
    mock_rss_scraper.return_value = mock_scraper_instance

    run_daily_scrape(time.time())

    # Should have created scraper instances
    assert mock_rss_scraper.called
```

**Step 2: Complete the implementation**

```python
# src/main.py (add to existing file after parse_args)

from src.scrapers.rss_scraper import RssScraper
from src.scrapers.arxiv_scraper import ArxivScraper
from src.scrapers.blog_scraper import BlogScraper
from src.scrapers.base import ScrapedArticle
from src.analyzers.claude import ClaudeProvider
from src.models.article import Article
from src.models.analysis import Analysis
from src.models.failed_task import FailedTask
from src.utils.sanitizer import generate_url_hash
from datetime import datetime, timezone

def check_timeout(start_time: float) -> bool:
    """Check if execution has exceeded max time"""
    elapsed = time.time() - start_time
    if elapsed >= MAX_EXECUTION_TIME:
        logger.warning("execution_timeout_reached", elapsed_seconds=elapsed)
        return True
    return False

def process_article_safe(
    scraped: ScrapedArticle,
    analyzer: ClaudeProvider,
    prompt: str,
    correlation_id: str
) -> bool:
    """Process a single article with error handling"""
    session = get_session()
    try:
        return process_article(session, scraped, analyzer, prompt, correlation_id)
    except Exception as e:
        logger.error("article_processing_failed",
                     url=scraped.url, error=str(e))
        record_failure(session, 'scrape', scraped.url, None, e)
        return False
    finally:
        session.close()

def process_article(
    session,
    scraped: ScrapedArticle,
    analyzer: ClaudeProvider,
    prompt: str,
    correlation_id: str
) -> bool:
    """Process and analyze a single article within a transaction"""
    # Generate URL hash for deduplication
    url_hash = generate_url_hash(scraped.url)

    # Check if article already exists
    existing = session.query(Article).filter_by(url_hash=url_hash).first()
    if existing:
        logger.info("article_already_exists", url=scraped.url)
        # Check if needs analysis
        if not has_analysis(session, existing.id):
            return analyze_article(session, existing, analyzer, prompt, correlation_id)
        return False

    # Create new article
    article = Article(
        url=scraped.url,
        url_hash=url_hash,
        source=scraped.source,
        title=scraped.title,
        content=scraped.content,
        published_at=parse_date(scraped.published_at),
        correlation_id=uuid.UUID(correlation_id),
        metadata_=scraped.metadata
    )

    session.add(article)
    session.flush()  # Get article ID

    # Analyze article
    success = analyze_article(session, article, analyzer, prompt, correlation_id)

    session.commit()
    logger.info("article_processed", url=scraped.url, article_id=str(article.id))

    return success

def analyze_article(
    session,
    article: Article,
    analyzer: ClaudeProvider,
    prompt: str,
    correlation_id: str
) -> bool:
    """Analyze an article using LLM"""
    result = analyzer.analyze(article.content, prompt)

    if result is None:
        record_failure(session, 'analyze', article.url, article.id,
                       Exception("Analysis returned None"))
        return False

    analysis = Analysis(
        article_id=article.id,
        correlation_id=uuid.UUID(correlation_id),
        tags=result.tags,
        pain_points=result.pain_points,
        insights=result.insights,
        innovations=result.innovations,
        model_used=LLM_MODEL,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens
    )

    session.add(analysis)
    logger.info("analysis_completed",
                article_id=str(article.id),
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens)

    return True

def record_failure(session, task_type: str, url: Optional[str],
                   article_id: Optional[uuid.UUID], error: Exception):
    """Record a failed task"""
    failure = FailedTask(
        task_type=task_type,
        article_url=url,
        article_id=article_id,
        exception_type=type(error).__name__,
        exception_message=str(error)
    )
    session.add(failure)
    session.commit()
    logger.error("failure_recorded", task_type=task_type, url=url)

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string to datetime"""
    if not date_str:
        return None
    try:
        # Try ISO format first
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        pass
    try:
        # Try RFC 2822 format (common in RSS)
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None

def load_prompt() -> str:
    """Load analysis prompt from file"""
    import os
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'analysis.txt')
    with open(prompt_path, 'r') as f:
        return f.read()

def run_daily_scrape(start_time: float):
    """Run daily scraping (RSS + arXiv)"""
    global _shutdown_requested

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    # Initialize analyzer
    analyzer = ClaudeProvider(api_key=LLM_API_KEY, model=LLM_MODEL)
    prompt = load_prompt()

    # Collect all articles
    all_articles: List[ScrapedArticle] = []

    # RSS sources
    from src.config import RSS_SOURCES
    for source_config in RSS_SOURCES:
        if _shutdown_requested or check_timeout(start_time):
            break
        scraper = RssScraper(url=source_config['url'], source=source_config['source'])
        articles = scraper.scrape()
        all_articles.extend(articles)
        logger.info("source_scraped", source=source_config['source'], count=len(articles))

    # arXiv
    if not _shutdown_requested and not check_timeout(start_time):
        arxiv_scraper = ArxivScraper()
        arxiv_articles = arxiv_scraper.scrape()
        all_articles.extend(arxiv_articles)
        logger.info("source_scraped", source="arxiv", count=len(arxiv_articles))

    # Limit batch size
    if len(all_articles) > BATCH_SIZE:
        logger.warning("batch_size_exceeded", total=len(all_articles), limit=BATCH_SIZE)
        all_articles = all_articles[:BATCH_SIZE]

    # Process with ThreadPoolExecutor
    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_article_safe, article, analyzer, prompt, correlation_id): article
            for article in all_articles
        }

        for future in as_completed(futures):
            if _shutdown_requested or check_timeout(start_time):
                logger.warning("processing_interrupted")
                break

            try:
                if future.result():
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
                logger.error("future_exception", error=str(e))

    logger.info("daily_scrape_completed",
                success=success_count,
                failures=failure_count,
                total=len(all_articles))

def run_weekly_scrape(start_time: float):
    """Run weekly scraping (blogs)"""
    global _shutdown_requested

    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    analyzer = ClaudeProvider(api_key=LLM_API_KEY, model=LLM_MODEL)
    prompt = load_prompt()

    all_articles: List[ScrapedArticle] = []

    from src.config import BLOG_SOURCES
    for source_config in BLOG_SOURCES:
        if _shutdown_requested or check_timeout(start_time):
            break
        scraper = BlogScraper(
            base_url=source_config['base_url'],
            source=source_config['source'],
            selectors=source_config['selectors']
        )
        articles = scraper.scrape()
        all_articles.extend(articles)
        logger.info("source_scraped", source=source_config['source'], count=len(articles))

    # Limit and process
    if len(all_articles) > BATCH_SIZE:
        all_articles = all_articles[:BATCH_SIZE]

    success_count = 0
    failure_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_article_safe, article, analyzer, prompt, correlation_id): article
            for article in all_articles
        }

        for future in as_completed(futures):
            if _shutdown_requested or check_timeout(start_time):
                break
            try:
                if future.result():
                    success_count += 1
                else:
                    failure_count += 1
            except Exception:
                failure_count += 1

    logger.info("weekly_scrape_completed", success=success_count, failures=failure_count)

def run_remediate():
    """Retry all unresolved failures"""
    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    session = get_session()

    # Find all unresolved failures
    failures = session.query(FailedTask).filter_by(resolved=False).all()

    if not failures:
        logger.info("no_failures_to_remediate")
        return

    analyzer = ClaudeProvider(api_key=LLM_API_KEY, model=LLM_MODEL)
    prompt = load_prompt()

    remediated = 0
    for failure in failures:
        if failure.task_type == 'analyze' and failure.article_id:
            article = session.query(Article).get(failure.article_id)
            if article and not has_analysis(session, article.id):
                if analyze_article(session, article, analyzer, prompt, correlation_id):
                    failure.resolved = True
                    failure.resolved_at = datetime.now(timezone.utc)
                    session.commit()
                    remediated += 1

    logger.info("remediation_completed", remediated=remediated, total=len(failures))
    session.close()
```

**Step 3: Run tests to verify they pass**

Run: `pytest tests/unit/test_main.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/main.py tests/unit/test_main.py
git commit -m "🔄 [FEAT] Implement run_daily_scrape, run_weekly_scrape, run_remediate with ThreadPoolExecutor"
```

---

### Task 8.11: Update architecture diagram — Phase 8

**Step 1: Render Phase 8 diagram**

Convert the **Phase 8 — Full System Architecture** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 8 (Full System Architecture)"
```

---

## Phase 9: Error Handling

### Task 9.1: Implement record_failure() function

**Files:**
- Modify: `src/main.py`
- Create: `tests/unit/test_error_handling.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_error_handling.py
import pytest
from unittest.mock import MagicMock, patch
import uuid

def test_record_failure_creates_failed_task():
    """record_failure should create a FailedTask record"""
    with patch('src.main.FailedTask') as MockFailedTask:
        from src.main import record_failure

        mock_session = MagicMock()
        mock_instance = MagicMock()
        MockFailedTask.return_value = mock_instance

        error = ValueError("Test error message")
        record_failure(mock_session, 'scrape', 'https://example.com', None, error)

        # Verify FailedTask was created with correct params
        MockFailedTask.assert_called_once()
        call_kwargs = MockFailedTask.call_args[1]
        assert call_kwargs['task_type'] == 'scrape'
        assert call_kwargs['article_url'] == 'https://example.com'
        assert call_kwargs['exception_type'] == 'ValueError'
        assert call_kwargs['exception_message'] == 'Test error message'

        # Verify it was added and committed
        mock_session.add.assert_called_once_with(mock_instance)
        mock_session.commit.assert_called_once()

def test_record_failure_with_article_id():
    """record_failure should store article_id when provided"""
    with patch('src.main.FailedTask') as MockFailedTask:
        from src.main import record_failure

        mock_session = MagicMock()
        article_id = uuid.uuid4()

        record_failure(mock_session, 'analyze', None, article_id, Exception("Analysis failed"))

        call_kwargs = MockFailedTask.call_args[1]
        assert call_kwargs['task_type'] == 'analyze'
        assert call_kwargs['article_id'] == article_id
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_error_handling.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/main.py (ensure record_failure function exists)

def record_failure(
    session,
    task_type: str,
    url: Optional[str],
    article_id: Optional[uuid.UUID],
    error: Exception
) -> None:
    """Record a failed task for later retry"""
    failure = FailedTask(
        task_type=task_type,
        article_url=url,
        article_id=article_id,
        exception_type=type(error).__name__,
        exception_message=str(error)
    )
    session.add(failure)
    session.commit()
    logger.error("failure_recorded",
                 task_type=task_type,
                 url=url,
                 error_type=type(error).__name__)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_error_handling.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/main.py tests/unit/test_error_handling.py
git commit -m "❌ [FEAT] Implement record_failure function"
```

---

### Task 9.2: Implement remediate command

**Files:**
- Modify: `src/main.py`
- Modify: `tests/unit/test_error_handling.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_error_handling.py (append)

@patch('src.main.get_session')
@patch('src.main.ClaudeProvider')
@patch('src.main.load_prompt')
def test_run_remediate_retries_failed_analyses(mock_prompt, mock_provider, mock_get_session):
    """run_remediate should retry failed analysis tasks"""
    from src.main import run_remediate
    from src.models.failed_task import FailedTask
    from src.models.article import Article

    # Setup mock session
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    # Setup mock failed task
    article_id = uuid.uuid4()
    mock_failed_task = MagicMock(spec=FailedTask)
    mock_failed_task.task_type = 'analyze'
    mock_failed_task.article_id = article_id
    mock_failed_task.resolved = False

    # Setup mock article
    mock_article = MagicMock(spec=Article)
    mock_article.id = article_id
    mock_article.content = "Test content"

    mock_session.query.return_value.filter_by.return_value.all.return_value = [mock_failed_task]
    mock_session.query.return_value.get.return_value = mock_article

    # Setup mock analyzer
    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = MagicMock(
        tags=['test'],
        pain_points='',
        insights='',
        innovations='',
        input_tokens=100,
        output_tokens=50
    )
    mock_provider.return_value = mock_analyzer
    mock_prompt.return_value = "test prompt"

    # Mock has_analysis to return False
    with patch('src.main.has_analysis', return_value=False):
        run_remediate()

    # Verify failure was marked as resolved
    assert mock_failed_task.resolved == True

@patch('src.main.get_session')
def test_run_remediate_skips_already_resolved(mock_get_session):
    """run_remediate should skip already resolved failures"""
    from src.main import run_remediate

    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    # No unresolved failures
    mock_session.query.return_value.filter_by.return_value.all.return_value = []

    run_remediate()

    # Should not attempt any processing
    mock_session.query.return_value.get.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_error_handling.py::test_run_remediate_retries_failed_analyses -v`
Expected: FAIL (if not yet implemented)

**Step 3: Verify implementation** (already in main.py from Phase 8)

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_error_handling.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_error_handling.py
git commit -m "🔧 [TEST] Add tests for remediate command"
```

---

### Task 9.3: Implement scan_missing_analyses() for zombie detection

**Files:**
- Modify: `src/database.py`
- Modify: `tests/unit/test_database.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_database.py (append)

def test_scan_missing_analyses_finds_zombie_records():
    """scan_missing_analyses should find articles without analysis"""
    from src.database import scan_missing_analyses
    from unittest.mock import MagicMock

    mock_session = MagicMock()

    # Mock article without analysis
    mock_article = MagicMock()
    mock_article.id = 'test-id'
    mock_article.url = 'https://example.com/zombie'

    mock_session.query.return_value.outerjoin.return_value.filter.return_value.all.return_value = [mock_article]

    result = scan_missing_analyses(mock_session)

    assert len(result) == 1
    assert result[0].url == 'https://example.com/zombie'

def test_scan_missing_analyses_excludes_recent():
    """scan_missing_analyses should only find articles older than threshold"""
    from src.database import scan_missing_analyses
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    mock_session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.all.return_value = []

    result = scan_missing_analyses(mock_session, min_age_hours=1)

    assert result == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_database.py::test_scan_missing_analyses_finds_zombie_records -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/database.py (append)

def scan_missing_analyses(session, min_age_hours: int = 1) -> List:
    """
    Find articles that should have analysis but don't (zombie records).
    Only considers articles older than min_age_hours to avoid race conditions.
    """
    from src.models.article import Article
    from src.models.analysis import Analysis

    cutoff = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)

    return session.query(Article)\
        .outerjoin(Analysis)\
        .filter(Analysis.id == None)\
        .filter(Article.scraped_at < cutoff)\
        .all()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_database.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/database.py tests/unit/test_database.py
git commit -m "👻 [FEAT] Implement scan_missing_analyses for zombie detection"
```

---

### Task 9.4-9.5: Integration tests for error handling

**Step 1: Commit** (if any additional changes)

```bash
git add src/main.py
git commit -m "❌ [FEAT] Implement record_failure and scan_missing_analyses"
```

---

### Task 9.4-9.5: Write integration tests for error handling

**Files:**
- Create: `tests/integration/test_error_handling.py`

**Step 1: Write integration test**

```python
# tests/integration/test_error_handling.py
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_session():
    """Create mock database session"""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    return session

def test_record_failure_creates_failed_task(mock_session):
    """record_failure should create FailedTask record"""
    from src.main import record_failure

    error = ValueError("Test error")
    record_failure(mock_session, 'scrape', 'https://example.com', None, error)

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()

    # Verify the FailedTask was created with correct fields
    call_args = mock_session.add.call_args
    failed_task = call_args[0][0]
    assert failed_task.task_type == 'scrape'
    assert failed_task.article_url == 'https://example.com'
    assert failed_task.exception_type == 'ValueError'
```

**Step 2: Commit**

```bash
git add tests/integration/test_error_handling.py
git commit -m "✅ [TEST] Add integration tests for error handling"
```

---

### Task 9.6: Update architecture diagram — Phase 9

**Step 1: Render Phase 9 diagram**

Convert the **Phase 9 — Error Handling Flow** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 9 (Error Handling)"
```

---

## Phase 10: Configuration

### Task 10.1: Implement config.py with environment variable loading

**Files:**
- Modify: `src/config.py`
- Create: `tests/unit/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_config.py
import pytest
import os
from unittest.mock import patch

def test_config_loads_database_url():
    """Config should load DATABASE_URL from environment"""
    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test:test@localhost/db'}):
        # Force reimport
        import importlib
        import src.config as config_module
        importlib.reload(config_module)

        assert config_module.DATABASE_URL == 'postgresql://test:test@localhost/db'

def test_config_loads_llm_settings():
    """Config should load LLM settings from environment"""
    with patch.dict(os.environ, {
        'LLM_API_KEY': 'sk-test-key',
        'LLM_PROVIDER': 'claude',
        'LLM_MODEL': 'claude-opus-4-5-20251101'
    }):
        import importlib
        import src.config as config_module
        importlib.reload(config_module)

        assert config_module.LLM_API_KEY == 'sk-test-key'
        assert config_module.LLM_PROVIDER == 'claude'
        assert config_module.LLM_MODEL == 'claude-opus-4-5-20251101'

def test_config_has_default_llm_model():
    """Config should have default LLM model if not set"""
    with patch.dict(os.environ, {'LLM_MODEL': ''}, clear=False):
        import importlib
        import src.config as config_module
        importlib.reload(config_module)

        # Should have a sensible default
        assert 'claude' in config_module.LLM_MODEL.lower() or config_module.LLM_MODEL == ''
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config.py -v`
Expected: FAIL (if config not yet complete)

**Step 3: Verify implementation exists** (from Task 4.7)

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_config.py
git commit -m "⚙️ [TEST] Add tests for environment variable loading"
```

---

### Task 10.2: Define source configurations

**Files:**
- Modify: `src/config.py`

Completed in Task 4.7 and Task 6.6. RSS_SOURCES and BLOG_SOURCES are defined.

**Step 1: Commit** (if any changes)

```bash
git add src/config.py
git commit -m "📋 [FEAT] Define complete source configurations"
```

---

### Task 10.3: Implement source loading by schedule_type

**Files:**
- Modify: `src/config.py`
- Modify: `tests/unit/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_config.py (append)

def test_get_sources_returns_rss_for_daily():
    """get_sources('daily') should return RSS sources"""
    from src.config import get_sources, RSS_SOURCES

    sources = get_sources('daily')

    assert sources == RSS_SOURCES
    assert len(sources) > 0
    assert all('url' in s for s in sources)

def test_get_sources_returns_blogs_for_weekly():
    """get_sources('weekly') should return blog sources"""
    from src.config import get_sources, BLOG_SOURCES

    sources = get_sources('weekly')

    assert sources == BLOG_SOURCES
    assert len(sources) > 0
    assert all('base_url' in s for s in sources)

def test_get_sources_returns_empty_for_unknown():
    """get_sources with unknown type should return empty list"""
    from src.config import get_sources

    sources = get_sources('unknown')
    assert sources == []

    sources = get_sources('')
    assert sources == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config.py::test_get_sources_returns_rss_for_daily -v`
Expected: FAIL (if get_sources not implemented)

**Step 3: Verify implementation exists** (from Task 4.7)

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_config.py
git commit -m "🔀 [TEST] Add tests for source loading by schedule_type"
```

---

### Task 10.4: Add configuration validation at startup

**Files:**
- Modify: `src/config.py`
- Modify: `tests/unit/test_config.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_config.py (append)

def test_validate_config_raises_on_missing_database_url():
    """validate_config should raise if DATABASE_URL is missing"""
    from src.config import validate_config
    import os

    with patch.dict(os.environ, {'DATABASE_URL': '', 'LLM_API_KEY': 'test'}):
        with pytest.raises(ValueError, match="DATABASE_URL"):
            validate_config()

def test_validate_config_raises_on_missing_api_key():
    """validate_config should raise if LLM_API_KEY is missing"""
    from src.config import validate_config
    import os

    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test', 'LLM_API_KEY': ''}):
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            validate_config()

def test_validate_config_passes_with_all_required():
    """validate_config should pass when all required vars are set"""
    from src.config import validate_config
    import os

    with patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://test:test@localhost/db',
        'LLM_API_KEY': 'sk-test-key'
    }):
        # Should not raise
        validate_config()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config.py::test_validate_config_raises_on_missing_database_url -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/config.py (add at the end)

def validate_config() -> None:
    """Validate required configuration at startup"""
    errors = []

    if not DATABASE_URL:
        errors.append("DATABASE_URL is required")

    if not LLM_API_KEY:
        errors.append("LLM_API_KEY is required")

    if LLM_PROVIDER not in ('claude', 'openai'):
        errors.append(f"LLM_PROVIDER must be 'claude' or 'openai', got '{LLM_PROVIDER}'")

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/config.py tests/unit/test_config.py
git commit -m "✅ [FEAT] Add configuration validation at startup"
```

---

### Task 10.5: Update architecture diagram — Phase 10

**Step 1: Render Phase 10 diagram**

Convert the **Phase 10 — Configuration** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 10 (Configuration)"
```

---

## Phase 11: Integration Testing

### Task 11.1: Verify docker-compose.yml supports integration tests

`docker-compose.yml` was created in Task 1.7 with both `app` and `postgres` services. Integration tests run inside the `app` container via `docker compose exec app pytest tests/integration/ -v`.

No new files needed. Skip to Task 11.2.

---

### Task 11.2-11.5: Write integration tests

**Files:**
- Create: `tests/integration/test_full_flow.py`
- Create: `tests/integration/conftest.py`

**Step 1: Write integration test fixtures**

```python
# tests/integration/conftest.py
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use test database
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost:5432/digital_twins_test'
os.environ['LLM_API_KEY'] = 'test-key'
os.environ['SKIP_CONFIG_VALIDATION'] = 'true'

@pytest.fixture(scope='session')
def db_engine():
    """Create database engine for tests"""
    from src.models.article import Base
    engine = create_engine(os.environ['DATABASE_URL'])
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(db_engine):
    """Create a new database session for each test"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
```

**Step 2: Write integration tests**

```python
# tests/integration/test_full_flow.py
import pytest
from unittest.mock import patch, MagicMock
import uuid

@pytest.mark.integration
def test_article_deduplication(db_session):
    """Duplicate articles should not be created"""
    from src.models.article import Article
    from src.utils.sanitizer import generate_url_hash

    url = "https://example.com/test-article"
    url_hash = generate_url_hash(url)

    # Create first article
    article1 = Article(
        url=url,
        url_hash=url_hash,
        source="test",
        title="Test Article",
        content="Test content",
        correlation_id=uuid.uuid4()
    )
    db_session.add(article1)
    db_session.commit()

    # Try to query for duplicate
    existing = db_session.query(Article).filter_by(url_hash=url_hash).first()
    assert existing is not None
    assert existing.url == url

@pytest.mark.integration
def test_transaction_rollback_on_failure(db_session):
    """Failed transactions should rollback completely"""
    from src.models.article import Article

    initial_count = db_session.query(Article).count()

    try:
        article = Article(
            url="https://example.com/rollback-test",
            url_hash="invalid",
            source="test",
            title="Test",
            content="Content",
            correlation_id=uuid.uuid4()
        )
        db_session.add(article)
        # Force an error
        raise ValueError("Simulated error")
    except ValueError:
        db_session.rollback()

    final_count = db_session.query(Article).count()
    assert final_count == initial_count
```

**Step 3: Commit**

```bash
git add tests/integration/
git commit -m "✅ [TEST] Add integration tests for full flow, transaction atomicity, and deduplication"
```

---

### Task 11.6: Update architecture diagram — Phase 11

**Step 1: Render Phase 11 diagram**

No diagram update needed — Phase 11 adds tests only, no new components. The existing `docs/architecture/digital-twins-scraper.drawio` (Phase 8 diagram) remains current.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 11 (Integration Tests)"
```

---

## Phase 12: Observability

### Task 12.1: Add structlog configuration with JSON output

**Files:**
- Modify: `src/utils/logging.py`
- Create: `tests/unit/test_observability.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_observability.py
import pytest
import json
from io import StringIO

def test_logger_outputs_valid_json(capsys):
    """Logger should output valid JSON"""
    from src.utils.logging import get_logger, configure_logging

    configure_logging()
    logger = get_logger("test")
    logger.info("test_event", key="value")

    captured = capsys.readouterr()
    log_line = captured.out.strip()

    # Should be valid JSON
    parsed = json.loads(log_line)
    assert parsed["event"] == "test_event"
    assert parsed["key"] == "value"

def test_logger_includes_timestamp(capsys):
    """Logger should include ISO timestamp"""
    from src.utils.logging import get_logger, configure_logging

    configure_logging()
    logger = get_logger("test")
    logger.info("test_event")

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert "timestamp" in parsed
    # ISO format check
    assert "T" in parsed["timestamp"]

def test_logger_includes_log_level(capsys):
    """Logger should include log level"""
    from src.utils.logging import get_logger, configure_logging

    configure_logging()
    logger = get_logger("test")
    logger.warning("warning_event")

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert parsed["level"] == "warning"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_observability.py -v`
Expected: FAIL (if not yet implemented)

**Step 3: Verify implementation** (from Phase 3)

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_observability.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_observability.py
git commit -m "📋 [TEST] Add tests for structlog JSON output"
```

---

### Task 12.2: Add correlation_id to all log entries

**Files:**
- Modify: `tests/unit/test_observability.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_observability.py (append)

def test_correlation_id_included_in_logs(capsys):
    """Logs should include correlation_id when bound"""
    from src.utils.logging import get_logger, configure_logging, bind_correlation_id

    configure_logging()
    bind_correlation_id("test-correlation-123")
    logger = get_logger("test")
    logger.info("event_with_correlation")

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert parsed["correlation_id"] == "test-correlation-123"

def test_correlation_id_propagates_across_loggers(capsys):
    """correlation_id should propagate to all loggers in same context"""
    from src.utils.logging import get_logger, configure_logging, bind_correlation_id

    configure_logging()
    bind_correlation_id("shared-correlation-456")

    logger1 = get_logger("module1")
    logger2 = get_logger("module2")

    logger1.info("event1")
    logger2.info("event2")

    captured = capsys.readouterr()
    lines = captured.out.strip().split('\n')

    for line in lines:
        parsed = json.loads(line)
        assert parsed["correlation_id"] == "shared-correlation-456"

def test_get_correlation_id_returns_current_value():
    """get_correlation_id should return currently bound value"""
    from src.utils.logging import bind_correlation_id, get_correlation_id

    bind_correlation_id("retrievable-id")
    assert get_correlation_id() == "retrievable-id"
```

**Step 2: Run test to verify it passes** (implementation from Phase 3)

Run: `pytest tests/unit/test_observability.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_observability.py
git commit -m "🔗 [TEST] Add tests for correlation_id in logs"
```

---

### Task 12.3: Add execution summary logging

**Files:**
- Modify: `src/utils/logging.py`
- Modify: `tests/unit/test_observability.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_observability.py (append)

def test_log_execution_summary_includes_all_metrics(capsys):
    """log_execution_summary should include all required metrics"""
    from src.utils.logging import log_execution_summary, configure_logging

    configure_logging()
    log_execution_summary(
        total_articles=100,
        success_count=95,
        failure_count=5,
        duration_seconds=120.5,
        total_tokens=50000
    )

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert parsed["event"] == "execution_summary"
    assert parsed["total_articles"] == 100
    assert parsed["success_count"] == 95
    assert parsed["failure_count"] == 5
    assert parsed["duration_seconds"] == 120.5
    assert parsed["total_tokens"] == 50000
    assert "articles_per_second" in parsed

def test_log_execution_summary_handles_zero_duration(capsys):
    """log_execution_summary should handle zero duration without division error"""
    from src.utils.logging import log_execution_summary, configure_logging

    configure_logging()
    # Should not raise ZeroDivisionError
    log_execution_summary(
        total_articles=10,
        success_count=10,
        failure_count=0,
        duration_seconds=0,
        total_tokens=1000
    )

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert parsed["articles_per_second"] == 10.0  # Uses max(duration, 1)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_observability.py::test_log_execution_summary_includes_all_metrics -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/utils/logging.py (append)

def log_execution_summary(
    total_articles: int,
    success_count: int,
    failure_count: int,
    duration_seconds: float,
    total_tokens: int = 0
) -> None:
    """Log execution summary metrics for monitoring dashboards"""
    logger = get_logger(__name__)
    logger.info(
        "execution_summary",
        total_articles=total_articles,
        success_count=success_count,
        failure_count=failure_count,
        duration_seconds=round(duration_seconds, 2),
        total_tokens=total_tokens,
        articles_per_second=round(total_articles / max(duration_seconds, 1), 2),
        success_rate=round(success_count / max(total_articles, 1) * 100, 1)
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_observability.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/utils/logging.py tests/unit/test_observability.py
git commit -m "📊 [FEAT] Add execution summary logging"
```

---

### Task 12.4: Add LLM metrics logging

**Files:**
- Modify: `src/utils/logging.py`
- Modify: `tests/unit/test_observability.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_observability.py (append)

def test_log_llm_metrics_includes_all_fields(capsys):
    """log_llm_metrics should include tokens and latency"""
    from src.utils.logging import log_llm_metrics, configure_logging

    configure_logging()
    log_llm_metrics(
        article_id="test-article-id",
        model="claude-sonnet-4-20250514",
        input_tokens=1500,
        output_tokens=300,
        latency_ms=2500
    )

    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())

    assert parsed["event"] == "llm_analysis_metrics"
    assert parsed["article_id"] == "test-article-id"
    assert parsed["model"] == "claude-sonnet-4-20250514"
    assert parsed["input_tokens"] == 1500
    assert parsed["output_tokens"] == 300
    assert parsed["total_tokens"] == 1800
    assert parsed["latency_ms"] == 2500
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_observability.py::test_log_llm_metrics_includes_all_fields -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# src/utils/logging.py (append)

def log_llm_metrics(
    article_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int
) -> None:
    """Log LLM metrics for cost monitoring and performance tracking"""
    logger = get_logger(__name__)
    logger.info(
        "llm_analysis_metrics",
        article_id=article_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        latency_ms=latency_ms
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_observability.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/utils/logging.py tests/unit/test_observability.py
git commit -m "📈 [FEAT] Add LLM metrics logging (tokens, latency)"
```

---

### Task 12.5: Add Sentry integration

**Files:**
- Modify: `src/main.py`

**Step 1: Add Sentry initialization**

```python
# src/main.py (add at top after imports)

from src.config import SENTRY_DSN

# Initialize Sentry if configured
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
    )
```

**Step 2: Commit**

```bash
git add src/main.py
git commit -m "🚨 [FEAT] Add optional Sentry integration"
```

---

### Task 12.6: Update architecture diagram — Phase 12

**Step 1: Render Phase 12 diagram**

Convert the **Phase 12 — Observability** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 2: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 12 (Observability)"
```

---

## Phase 13: Deployment

### Task 13.1: Test Docker build locally

**Step 1: Build and test**

```bash
docker build -t digital-twins-scraper .
# Dry run - just verify it builds
```

**Step 2: Commit** (no code changes, just verification)

---

### Task 13.2-13.4: Railway setup documentation

**Files:**
- Create: `DEPLOYMENT.md`

**Step 1: Write deployment documentation**

```markdown
# Deployment Guide

## Railway Setup

1. Create a new Railway project
2. Add PostgreSQL database from Railway marketplace
3. Set environment variables:
   - `DATABASE_URL`: Automatically set by Railway PostgreSQL
   - `LLM_API_KEY`: Your Anthropic API key
   - `LLM_PROVIDER`: claude
   - `LLM_MODEL`: claude-sonnet-4-20250514
   - `SENTRY_DSN`: (optional) Sentry DSN for error tracking

## Cron Jobs

Create two cron jobs in Railway:

### Daily Scraper
- Schedule: `0 8 * * *` (8:00 AM UTC daily)
- Command: `python -m src.main daily`

### Weekly Scraper
- Schedule: `0 8 * * 1` (8:00 AM UTC Monday)
- Command: `python -m src.main weekly`

## Database Migrations

Run migrations manually via Railway CLI:
```bash
railway run psql $DATABASE_URL -f migrations/001_initial.sql
```

## Verification

1. Check Railway logs for execution output
2. Query database to verify articles and analyses
3. Monitor Grafana Cloud (if configured) for metrics
```

**Step 2: Commit**

```bash
git add DEPLOYMENT.md
git commit -m "📚 [DOCS] Add deployment documentation for Railway"
```

---

### Task 13.5-13.6: Cron job configuration

Documented in DEPLOYMENT.md above.

---

### Task 13.7-13.9: Final verification

Manual steps documented in DEPLOYMENT.md.

---

### Task 13.10: Update architecture diagram — Phase 13

**Step 1: Create the directory (first time only)**

```bash
mkdir -p docs/architecture
```

**Step 2: Render Phase 13 diagram**

Convert the **Phase 13 — Complete Deployment Architecture** Mermaid diagram from the [Appendix](#appendix-phase-architecture-diagrams) into drawio XML and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool.

**Step 3: Commit**

```bash
git add docs/architecture/
git commit -m "📐 [DOCS] Update architecture diagram — Phase 13 (Final)"
```

---

## Execution Summary

| Phase | Tasks | Commits | Drawio Task |
|-------|-------|---------|-------------|
| 1. Project Setup | 1.1-1.7 | 7 | 1.8 |
| 2. Database Layer | 2.1-2.7 | 7 | 2.8 |
| 3. Utilities | 3.1-3.5 | 5 | 3.6 |
| 4. RSS Scraper | 4.1-4.9 | 4 | 4.10 |
| 5. arXiv Scraper | 5.1-5.6 | 2 | 5.7 |
| 6. Blog Scraper | 6.1-6.7 | 2 | 6.8 |
| 7. LLM Analyzer | 7.1-7.8 | 4 | 7.9 |
| 8. Main Flow | 8.1-8.10 | 2 | 8.11 |
| 9. Error Handling | 9.1-9.5 | 2 | 9.6 |
| 10. Configuration | 10.1-10.4 | 1 | 10.5 |
| 11. Integration Tests | 11.1-11.5 | 2 | 11.6 |
| 12. Observability | 12.1-12.5 | 2 | 12.6 |
| 13. Deployment | 13.1-13.9 | 1 | 13.10 |

**Total: ~53 commits** (40 original + 13 drawio diagram updates)

---

## Verification Commands

```bash
# Run all unit tests
pytest tests/unit -v --cov=src --cov-fail-under=80

# Run integration tests (requires Docker)
docker-compose up -d postgres
pytest tests/integration -v -m integration
docker-compose down

# Build Docker image
docker build -t digital-twins-scraper .

# Test locally
docker run --env-file .env digital-twins-scraper python -m src.main daily
```

---

## Appendix: Phase Architecture Diagrams

> **For Claude:** Convert the Mermaid diagram for the current phase into drawio XML (`mxGraphModel` format) and write it directly to `docs/architecture/digital-twins-scraper.drawio` using the Write tool. Each phase overwrites the file with a progressively richer diagram.

### Phase 1 — Project Setup

```mermaid
graph TB
    subgraph "Digital Twins Scraper"
        subgraph "src/ (placeholders)"
            main["main.py"]
            config["config.py"]
            database["database.py"]
            models_dir["models/"]
            scrapers_dir["scrapers/"]
            analyzers_dir["analyzers/"]
            utils_dir["utils/"]
            prompts_dir["prompts/"]
        end

        subgraph "Infrastructure"
            dockerfile["Dockerfile"]
            railway["railway.toml"]
            compose["docker-compose.yml"]
            devdocker["Dockerfile.dev"]
            requirements["requirements.txt"]
        end

        subgraph "Tests"
            unit["tests/unit/"]
            integration["tests/integration/"]
            conftest["tests/conftest.py"]
            pytestini["pytest.ini"]
        end
    end

    compose -->|"builds"| devdocker
    compose -->|"depends_on"| pg[("PostgreSQL 15")]

    style main fill:#ddd,stroke:#999
    style config fill:#ddd,stroke:#999
    style database fill:#ddd,stroke:#999
    style models_dir fill:#ddd,stroke:#999
    style scrapers_dir fill:#ddd,stroke:#999
    style analyzers_dir fill:#ddd,stroke:#999
    style utils_dir fill:#ddd,stroke:#999
    style prompts_dir fill:#ddd,stroke:#999
```

---

### Phase 2 — Database Layer

```mermaid
graph TB
    subgraph "Database Layer"
        db["database.py<br/>─────────<br/>create_engine_with_nullpool()<br/>get_engine() / get_session()<br/>has_analysis()<br/>find_missing_analyses()<br/>find_recent_failures()"]

        subgraph "Models"
            article["Article<br/>─────────<br/>id: UUID PK<br/>url: Text UNIQUE<br/>url_hash: String(64)<br/>source: String(50)<br/>title / content: Text<br/>published_at / scraped_at<br/>metadata: JSONB<br/>correlation_id: UUID"]

            analysis["Analysis<br/>─────────<br/>id: UUID PK<br/>article_id: UUID FK UNIQUE<br/>correlation_id: UUID<br/>tags: TEXT[]<br/>pain_points / insights<br/>innovations: Text<br/>model_used: String<br/>input_tokens / output_tokens"]

            failed["FailedTask<br/>─────────<br/>id: UUID PK<br/>task_type: String<br/>article_url / article_id<br/>exception_type / message<br/>failed_at / resolved"]
        end

        pg[("PostgreSQL 15<br/>(NullPool)")]
    end

    migrations["migrations/001_initial.sql"]

    db -->|NullPool| pg
    analysis -->|"FK article_id"| article
    failed -.->|"FK article_id"| article
    migrations -.->|"CREATE TABLE"| pg

    style db fill:#4CAF50,color:#fff
    style article fill:#2196F3,color:#fff
    style analysis fill:#2196F3,color:#fff
    style failed fill:#FF9800,color:#fff
    style pg fill:#336791,color:#fff
```

---

### Phase 3 — Utilities

```mermaid
graph TB
    subgraph "Utilities"
        logging["utils/logging.py<br/>─────────<br/>configure_logging()<br/>get_logger()<br/>bind_correlation_id()<br/>get_correlation_id()"]

        sanitizer["utils/sanitizer.py<br/>─────────<br/>sanitize_content()<br/>generate_url_hash()<br/>MAX_CONTENT_LENGTH=50K"]
    end

    subgraph "Database Layer"
        db["database.py"]
        models["Article | Analysis | FailedTask"]
        pg[("PostgreSQL 15")]
    end

    logging -->|"structlog JSON"| stdout["stdout (Railway logs)"]
    db -->|NullPool| pg

    style logging fill:#9C27B0,color:#fff
    style sanitizer fill:#9C27B0,color:#fff
    style db fill:#4CAF50,color:#fff
    style models fill:#2196F3,color:#fff
    style pg fill:#336791,color:#fff
```

---

### Phase 4 — RSS Scraper

```mermaid
graph TB
    subgraph "Scraper Layer"
        base["BaseScraper (ABC)<br/>+ scrape() -> List[ScrapedArticle]"]
        scraped["ScrapedArticle (dataclass)<br/>url, title, content<br/>published_at, source, metadata"]
        rss["RssScraper<br/>─────────<br/>+ scrape()<br/>+ _matches_keywords()<br/>DIGITAL_TWINS_KEYWORDS<br/>rate_limit: 1.0s"]
    end

    subgraph "Config"
        config["config.py<br/>RSS_SOURCES:<br/>techcrunch / venturebeat<br/>iotworldtoday"]
    end

    subgraph "External"
        feeds["RSS Feeds (HTTP GET)"]
    end

    subgraph "Utilities"
        sanitizer["sanitizer.py"]
        logging["logging.py"]
    end

    subgraph "Database Layer"
        db["database.py"]
        pg[("PostgreSQL 15")]
    end

    rss -->|inherits| base
    base -->|returns| scraped
    rss -->|"fetch + feedparser"| feeds
    rss -->|sanitize_content| sanitizer
    config -.->|sources| rss

    style base fill:#E91E63,color:#fff
    style rss fill:#E91E63,color:#fff
    style scraped fill:#F48FB1,color:#000
    style config fill:#607D8B,color:#fff
    style db fill:#4CAF50,color:#fff
    style pg fill:#336791,color:#fff
```

---

### Phase 5 — arXiv Scraper

```mermaid
graph TB
    subgraph "Scraper Layer"
        base["BaseScraper (ABC)"]
        rss["RssScraper"]
        arxiv["ArxivScraper<br/>─────────<br/>+ scrape()<br/>+ _build_query()<br/>max_results: 100<br/>days_back: 7"]
    end

    subgraph "External"
        feeds["RSS Feeds"]
        arxiv_api["arXiv API (Atom XML)<br/>export.arxiv.org"]
    end

    rss -->|inherits| base
    arxiv -->|inherits| base
    rss --> feeds
    arxiv -->|"search_query params"| arxiv_api

    style base fill:#E91E63,color:#fff
    style rss fill:#E91E63,color:#fff
    style arxiv fill:#E91E63,color:#fff
    style arxiv_api fill:#FF5722,color:#fff
```

---

### Phase 6 — Complete Scraper Layer

```mermaid
graph TB
    subgraph "Scraper Layer"
        base["BaseScraper (ABC)<br/>+ scrape() -> List[ScrapedArticle]"]
        scraped["ScrapedArticle (dataclass)"]
        rss["RssScraper<br/>keyword filtering"]
        arxiv["ArxivScraper<br/>Atom XML + date filter"]
        blog["BlogScraper<br/>CSS selectors<br/>robots.txt check<br/>rate_limit: 2.0s"]
    end

    subgraph "Config"
        config["config.py<br/>─────────<br/>RSS_SOURCES: 3 feeds<br/>BLOG_SOURCES: 4 blogs<br/>(NVIDIA, Siemens,<br/>AWS IoT, Azure IoT)"]
    end

    subgraph "External"
        feeds["RSS Feeds"]
        arxiv_api["arXiv API"]
        blogs["Tech Blogs (HTML)"]
        robots["robots.txt"]
    end

    subgraph "Utilities"
        sanitizer["sanitizer.py"]
        logging["logging.py"]
    end

    subgraph "Database Layer"
        db["database.py (NullPool)"]
        models["Article | Analysis | FailedTask"]
        pg[("PostgreSQL 15")]
    end

    rss -->|inherits| base
    arxiv -->|inherits| base
    blog -->|inherits| base
    base -->|returns| scraped

    rss --> feeds
    arxiv --> arxiv_api
    blog --> blogs
    blog -.->|check| robots
    rss --> sanitizer
    blog --> sanitizer
    config -.-> rss
    config -.-> blog
    db --> pg

    style base fill:#E91E63,color:#fff
    style rss fill:#E91E63,color:#fff
    style arxiv fill:#E91E63,color:#fff
    style blog fill:#E91E63,color:#fff
    style config fill:#607D8B,color:#fff
    style sanitizer fill:#9C27B0,color:#fff
    style logging fill:#9C27B0,color:#fff
    style db fill:#4CAF50,color:#fff
    style models fill:#2196F3,color:#fff
    style pg fill:#336791,color:#fff
```

---

### Phase 7 — LLM Analyzer

```mermaid
graph TB
    subgraph "Analyzer Layer"
        llm_base["LLMProvider (ABC)<br/>+ analyze(content, prompt)<br/>-> AnalysisResult"]
        result["AnalysisResult (dataclass)<br/>tags, pain_points, insights<br/>innovations, input/output_tokens"]
        claude["ClaudeProvider<br/>─────────<br/>+ analyze() / _call_api()<br/>+ _validate_response()<br/>retry: 3x exponential 4-60s"]
        prompt["prompts/analysis.txt<br/>→ JSON output format"]
    end

    subgraph "External"
        anthropic_api["Anthropic API<br/>Claude Sonnet"]
    end

    subgraph "Scraper Layer"
        scrapers["RssScraper | ArxivScraper | BlogScraper"]
    end

    subgraph "Database Layer"
        db["database.py"]
        models["Article | Analysis | FailedTask"]
        pg[("PostgreSQL 15")]
    end

    claude -->|inherits| llm_base
    llm_base -->|returns| result
    claude -->|"messages.create()"| anthropic_api
    claude -->|reads| prompt
    scrapers -->|ScrapedArticle| models
    result -->|"stored as"| models
    db --> pg

    style llm_base fill:#FF9800,color:#fff
    style claude fill:#FF9800,color:#fff
    style result fill:#FFE0B2,color:#000
    style prompt fill:#FFF3E0,color:#000
    style anthropic_api fill:#1A1A2E,color:#fff
    style scrapers fill:#E91E63,color:#fff
    style db fill:#4CAF50,color:#fff
    style models fill:#2196F3,color:#fff
    style pg fill:#336791,color:#fff
```

---

### Phase 8 — Full System Architecture

```mermaid
graph TB
    subgraph "Entry Point"
        cli["main.py CLI<br/>daily | weekly | remediate"]
        signal["Signal Handler<br/>SIGTERM / SIGINT"]
    end

    subgraph "Execution Engine"
        daily["run_daily_scrape()<br/>RSS + arXiv"]
        weekly["run_weekly_scrape()<br/>Blogs"]
        remediate["run_remediate()<br/>Retry failures"]
        pool["ThreadPoolExecutor<br/>max_workers=3"]
        process["process_article_safe()<br/>→ process_article()<br/>→ analyze_article()"]
        timeout["check_timeout()<br/>MAX=50 min"]
    end

    subgraph "Scraper Layer"
        rss["RssScraper"]
        arxiv["ArxivScraper"]
        blog["BlogScraper"]
    end

    subgraph "Analyzer Layer"
        claude["ClaudeProvider<br/>retry: 3x"]
        prompt["analysis.txt"]
    end

    subgraph "Database Layer"
        db["database.py (NullPool)"]
        article_m["Article"]
        analysis_m["Analysis"]
        failed_m["FailedTask"]
        pg[("PostgreSQL 15")]
    end

    subgraph "Utilities"
        logging["structlog JSON + correlation_id"]
        sanitizer["sanitizer + url_hash"]
    end

    subgraph "Config"
        config["config.py<br/>RSS_SOURCES / BLOG_SOURCES<br/>LLM_API_KEY / DATABASE_URL"]
    end

    subgraph "External"
        feeds["RSS Feeds"]
        arxiv_api["arXiv API"]
        blogs["Tech Blogs"]
        anthropic["Anthropic API"]
    end

    cli --> daily & weekly & remediate
    signal -.-> cli
    daily --> rss & arxiv
    weekly --> blog
    daily & weekly --> pool --> process
    process --> timeout

    rss --> feeds
    arxiv --> arxiv_api
    blog --> blogs

    process -->|"1. dedup"| sanitizer
    process -->|"2. save"| db
    process -->|"3. analyze"| claude
    process -->|"4. store"| db
    process -->|"on error"| failed_m

    claude --> anthropic
    claude --> prompt
    remediate -->|"retry"| failed_m
    db --> pg
    config -.-> cli
    logging -.-> cli

    style cli fill:#673AB7,color:#fff
    style daily fill:#673AB7,color:#fff
    style weekly fill:#673AB7,color:#fff
    style remediate fill:#673AB7,color:#fff
    style pool fill:#512DA8,color:#fff
    style process fill:#512DA8,color:#fff
    style rss fill:#E91E63,color:#fff
    style arxiv fill:#E91E63,color:#fff
    style blog fill:#E91E63,color:#fff
    style claude fill:#FF9800,color:#fff
    style db fill:#4CAF50,color:#fff
    style article_m fill:#2196F3,color:#fff
    style analysis_m fill:#2196F3,color:#fff
    style failed_m fill:#FF9800,color:#fff
    style pg fill:#336791,color:#fff
    style config fill:#607D8B,color:#fff
```

---

### Phase 9 — Error Handling Flow

Use the Phase 8 diagram as base. Add this error handling detail overlay:

```mermaid
graph LR
    subgraph "Error Handling Flow"
        process["process_article_safe()"]
        record["record_failure()<br/>→ FailedTask"]
        scan["scan_missing_analyses()<br/>→ zombie articles"]
        remediate["run_remediate()<br/>→ retry"]
    end

    subgraph "Database"
        failed["FailedTask (resolved: bool)"]
        article["Article (no Analysis)"]
    end

    process -->|"exception"| record -->|"INSERT"| failed
    scan -->|"OUTER JOIN IS NULL"| article
    remediate -->|"query resolved=false"| failed
    remediate -->|"retry analyze"| article

    style record fill:#f44336,color:#fff
    style scan fill:#FF9800,color:#fff
    style remediate fill:#4CAF50,color:#fff
```

---

### Phase 10 — Configuration

Use the Phase 8 diagram. Add `validate_config()` to the Config box:

```
config.py
  + validate_config()  ← raises ValueError if DATABASE_URL or LLM_API_KEY missing
```

No new Mermaid diagram needed — update the Phase 8 diagram's Config box to include `validate_config()`.

---

### Phase 11 — Integration Tests

No architecture changes. Use Phase 8 diagram unchanged.

---

### Phase 12 — Observability

Use the Phase 8 diagram as base. Update the Utilities box:

```mermaid
graph TB
    subgraph "Observability"
        structlog["structlog JSON<br/>─────────<br/>configure_logging()<br/>get_logger()<br/>bind_correlation_id()<br/>log_execution_summary()<br/>log_llm_metrics()"]
        sentry["Sentry SDK<br/>traces_sample_rate=0.1"]
    end

    subgraph "Outputs"
        railway_logs["Railway Logs (stdout JSON)"]
        sentry_dash["Sentry Dashboard"]
    end

    structlog -->|"JSON lines"| railway_logs
    sentry -->|"errors + traces"| sentry_dash

    style structlog fill:#9C27B0,color:#fff
    style sentry fill:#362D59,color:#fff
```

---

### Phase 13 — Complete Deployment Architecture

```mermaid
graph TB
    subgraph "Railway Platform"
        subgraph "Cron Jobs"
            daily_cron["Daily: 0 8 * * *<br/>python -m src.main daily"]
            weekly_cron["Weekly: 0 8 * * 1<br/>python -m src.main weekly"]
        end

        subgraph "App Container (Python 3.11-slim)"
            cli["main.py CLI"]
            pool["ThreadPoolExecutor (3)"]

            subgraph "Scrapers"
                s1["RssScraper"]
                s2["ArxivScraper"]
                s3["BlogScraper"]
            end

            subgraph "Analyzer"
                claude["ClaudeProvider (3x retry)"]
            end

            subgraph "Utils"
                log["structlog JSON"]
                san["sanitizer"]
                sentry["Sentry SDK"]
            end
        end

        pg[("Railway PostgreSQL 15<br/>NullPool")]
    end

    subgraph "External Sources"
        rss["RSS: TechCrunch,<br/>VentureBeat, IoT World"]
        arxiv["arXiv API"]
        blogs["Blogs: NVIDIA, Siemens,<br/>AWS IoT, Azure IoT"]
    end

    subgraph "External Services"
        anthropic["Anthropic API<br/>Claude Sonnet"]
        sentry_dash["Sentry Dashboard"]
    end

    daily_cron & weekly_cron --> cli --> pool
    pool --> s1 & s2 & s3 & claude

    s1 --> rss
    s2 --> arxiv
    s3 --> blogs
    claude --> anthropic
    sentry -.-> sentry_dash

    cli -->|"Article + Analysis"| pg

    style daily_cron fill:#673AB7,color:#fff
    style weekly_cron fill:#673AB7,color:#fff
    style cli fill:#1A237E,color:#fff
    style pg fill:#336791,color:#fff
    style s1 fill:#E91E63,color:#fff
    style s2 fill:#E91E63,color:#fff
    style s3 fill:#E91E63,color:#fff
    style claude fill:#FF9800,color:#fff
    style anthropic fill:#1A1A2E,color:#fff
    style log fill:#9C27B0,color:#fff
    style san fill:#9C27B0,color:#fff
    style sentry fill:#362D59,color:#fff
```

---

### Drawio Write Tool Reference

**Tool:** Write tool (drawio files are `mxGraphModel` XML)

Convert the Mermaid diagram for the current phase into drawio XML and write it to `docs/architecture/digital-twins-scraper.drawio`. Each phase overwrites the previous diagram with a progressively richer version.

```
Write tool target: docs/architecture/digital-twins-scraper.drawio
Format: mxGraphModel XML (standard drawio file format)
```
