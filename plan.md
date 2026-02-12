# Digital Twins Scraper - TDD 實作計畫 (Railway 版本)

本計畫遵循 TDD（Test-Driven Development）流程：
1. 寫測試（先失敗）
2. 寫最精簡實作（讓測試通過）
3. 重構（如需要）
4. Git commit

**Commit Message 格式**: `<random_emoji> [FEAT|FIX|TEST|DOCS] <actual_message>`

**技術棧**:
- Platform: Railway (Cron Jobs)
- Database: PostgreSQL (Railway 託管)
- Language: Python 3.11
- ORM: SQLAlchemy with NullPool
- LLM: Claude API (Anthropic)
- Testing: pytest, pytest-cov

---

## Phase 1: Project Setup

### Task 1.1: Initialize Python project

**更動檔案**: `requirements.txt`

**內容**:
```
# Core
sqlalchemy>=2.0
psycopg2-binary
beautifulsoup4
requests
feedparser
anthropic
tenacity
structlog

# Testing
pytest
pytest-cov
responses

# Optional
sentry-sdk
```

**驗證**:
```bash
pip install -r requirements.txt
```

**Git commit**: `🚀 [FEAT] Initialize Python project with requirements.txt`

---

### Task 1.2: Create src/ directory structure

**更動檔案**: 建立目錄結構
```
src/
├── __init__.py
├── main.py
├── config.py
├── database.py
├── models/
│   ├── __init__.py
│   ├── article.py
│   ├── analysis.py
│   └── failed_task.py
├── scrapers/
│   ├── __init__.py
│   ├── base.py
│   ├── rss_scraper.py
│   ├── arxiv_scraper.py
│   └── blog_scraper.py
├── analyzers/
│   ├── __init__.py
│   ├── llm_provider.py
│   └── claude.py
├── utils/
│   ├── __init__.py
│   ├── sanitizer.py
│   └── logging.py
└── prompts/
    └── analysis.txt
```

**驗證**:
```bash
python -c "import src"
```

**Git commit**: `📁 [FEAT] Create src/ directory structure`

---

### Task 1.3: Create Dockerfile

**更動檔案**: `Dockerfile`

**內容**:
```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "-m", "src.main", "daily"]
```

**驗證**:
```bash
docker build -t digital-twins-scraper .
```

**Git commit**: `🐳 [FEAT] Add Dockerfile with PYTHONUNBUFFERED=1`

---

### Task 1.4: Create railway.toml

**更動檔案**: `railway.toml`

**內容**:
```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"
```

**Git commit**: `🚂 [FEAT] Add railway.toml for build configuration`

---

### Task 1.5: Create .env.example

**更動檔案**: `.env.example`

**內容**:
```
DATABASE_URL=postgresql://user:password@localhost:5432/digital_twins
LLM_API_KEY=sk-ant-...
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-20250514
SENTRY_DSN=
```

**Git commit**: `🔐 [DOCS] Add .env.example with required environment variables`

---

### Task 1.6: Set up pytest

**更動檔案**:
- `tests/__init__.py`
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/conftest.py`
- `pytest.ini`

**pytest.ini 內容**:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

**驗證**:
```bash
pytest --collect-only
```

**Git commit**: `🧪 [TEST] Set up pytest and test directory structure`

---

## Phase 2: Database Layer (TDD)

### Task 2.1: Implement database.py with NullPool

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_database.py`):
```python
import pytest

def test_engine_uses_nullpool():
    """Engine should use NullPool to avoid connection leaks"""
    from src.database import engine
    from sqlalchemy.pool import NullPool
    assert isinstance(engine.pool, NullPool)

def test_get_session_returns_session():
    """get_session should return a valid SQLAlchemy session"""
    from src.database import get_session
    session = get_session()
    assert session is not None
    session.close()
```

2. **確認測試失敗**: `pytest tests/unit/test_database.py` → FAILED

3. **寫最精簡實作** (`src/database.py`):
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from src.config import DATABASE_URL

engine = create_engine(DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(bind=engine)

def get_session():
    return SessionLocal()
```

4. **確認測試通過**: `pytest tests/unit/test_database.py` → PASSED

5. **Git commit**: `🗄️ [FEAT] Implement database.py with SQLAlchemy NullPool`

---

### Task 2.2: Create Article model

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_models.py`):
```python
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
    assert hasattr(Article, 'correlation_id')

def test_article_url_hash_is_unique():
    """Article url_hash should have unique constraint"""
    from src.models.article import Article
    # Check table has url_hash column with unique constraint
    for constraint in Article.__table__.constraints:
        if hasattr(constraint, 'columns'):
            col_names = [c.name for c in constraint.columns]
            if 'url_hash' in col_names:
                return  # Found unique constraint
    pytest.fail("No unique constraint found on url_hash")
```

2. **確認測試失敗**: `pytest tests/unit/test_models.py::test_article_model_has_required_fields` → FAILED

3. **寫最精簡實作** (`src/models/article.py`):
```python
from sqlalchemy import Column, String, Text, DateTime, UniqueConstraint, Index
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
    metadata = Column(JSONB)
    correlation_id = Column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint('url_hash', name='unique_url_hash'),
        Index('idx_articles_source', 'source'),
        Index('idx_articles_scraped_at', 'scraped_at'),
    )
```

4. **確認測試通過**: `pytest tests/unit/test_models.py` → PASSED

5. **Git commit**: `📝 [FEAT] Create Article model with all fields and constraints`

---

### Task 2.3: Create Analysis model

**TDD 步驟**:

1. **寫測試** (新增到 `tests/unit/test_models.py`):
```python
def test_analysis_model_has_required_fields():
    """Analysis model should have all required fields"""
    from src.models.analysis import Analysis
    assert hasattr(Analysis, 'id')
    assert hasattr(Analysis, 'article_id')
    assert hasattr(Analysis, 'tags')
    assert hasattr(Analysis, 'pain_points')
    assert hasattr(Analysis, 'insights')
    assert hasattr(Analysis, 'innovations')
    assert hasattr(Analysis, 'model_used')

def test_analysis_has_foreign_key_to_article():
    """Analysis should have foreign key to Article"""
    from src.models.analysis import Analysis
    fk_tables = [fk.column.table.name for fk in Analysis.__table__.foreign_keys]
    assert 'articles' in fk_tables
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/models/analysis.py`):
```python
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from src.models.article import Base

class Analysis(Base):
    __tablename__ = 'analyses'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey('articles.id'), nullable=False)
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
        UniqueConstraint('article_id', name='unique_article_analysis'),
        Index('idx_analyses_article_id', 'article_id'),
        Index('idx_analyses_analyzed_at', 'analyzed_at'),
    )
```

4. **確認測試通過**

5. **Git commit**: `📊 [FEAT] Create Analysis model with foreign key to Article`

---

### Task 2.4: Create FailedTask model

**TDD 步驟**:

1. **寫測試**:
```python
def test_failed_task_model_has_required_fields():
    """FailedTask model should have required fields"""
    from src.models.failed_task import FailedTask
    assert hasattr(FailedTask, 'id')
    assert hasattr(FailedTask, 'task_type')
    assert hasattr(FailedTask, 'article_url')
    assert hasattr(FailedTask, 'exception_message')
    assert hasattr(FailedTask, 'resolved')
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/models/failed_task.py`):
```python
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
    )
```

4. **確認測試通過**

5. **Git commit**: `❌ [FEAT] Create FailedTask model for error tracking`

---

### Task 2.5: Create database migration scripts

**更動檔案**: `migrations/001_initial.sql`

**內容**:
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
    correlation_id UUID NOT NULL,
    CONSTRAINT unique_url_hash UNIQUE (url_hash)
);

CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_scraped_at ON articles(scraped_at);
CREATE INDEX idx_articles_correlation_id ON articles(correlation_id);

CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID NOT NULL REFERENCES articles(id),
    correlation_id UUID NOT NULL,
    tags TEXT[] NOT NULL,
    pain_points TEXT,
    insights TEXT,
    innovations TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    model_used VARCHAR(100) NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    CONSTRAINT unique_article_analysis UNIQUE (article_id)
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
```

**Git commit**: `🔄 [FEAT] Add database migration scripts`

---

### Task 2.6: Write unit tests for models

**更動檔案**: 補充 `tests/unit/test_models.py`

**Git commit**: `✅ [TEST] Add comprehensive unit tests for models`

---

### Task 2.7: Implement helper functions

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_database.py` 新增):
```python
import pytest
from datetime import datetime, timedelta, timezone

def test_has_analysis_returns_true_when_exists(db_session, sample_article, sample_analysis):
    """has_analysis should return True when analysis exists"""
    from src.database import has_analysis
    db_session.add(sample_article)
    db_session.add(sample_analysis)
    db_session.commit()

    result = has_analysis(db_session, sample_article.id)
    assert result is True

def test_has_analysis_returns_false_when_not_exists(db_session, sample_article):
    """has_analysis should return False when no analysis"""
    from src.database import has_analysis
    db_session.add(sample_article)
    db_session.commit()

    result = has_analysis(db_session, sample_article.id)
    assert result is False

def test_find_missing_analyses_returns_articles_without_analysis(db_session, sample_article):
    """find_missing_analyses should return articles without analysis"""
    from src.database import find_missing_analyses
    db_session.add(sample_article)
    db_session.commit()

    missing = find_missing_analyses(db_session)
    assert len(missing) == 1
    assert missing[0].id == sample_article.id

def test_find_recent_failures_returns_unresolved_within_24h(db_session):
    """find_recent_failures should return failures from last 24h"""
    from src.database import find_recent_failures
    from src.models.failed_task import FailedTask

    recent = FailedTask(task_type='analyze', failed_at=datetime.now(timezone.utc))
    old = FailedTask(task_type='analyze', failed_at=datetime.now(timezone.utc) - timedelta(hours=25))
    db_session.add_all([recent, old])
    db_session.commit()

    failures = find_recent_failures(db_session)
    assert len(failures) == 1
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/database.py` 新增):
```python
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from src.models.article import Article
from src.models.analysis import Analysis
from src.models.failed_task import FailedTask

def has_analysis(session, article_id: UUID) -> bool:
    """Check if article has analysis"""
    return session.query(Analysis).filter_by(article_id=article_id).first() is not None

def find_missing_analyses(session) -> List[Article]:
    """Find articles without analysis"""
    return session.query(Article).outerjoin(Analysis).filter(Analysis.id == None).all()

def find_recent_failures(session, hours: int = 24) -> List[FailedTask]:
    """Find unresolved failures from last N hours"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return session.query(FailedTask).filter(
        FailedTask.resolved == False,
        FailedTask.failed_at >= cutoff
    ).all()
```

4. **確認測試通過**

5. **Git commit**: `🔍 [FEAT] Implement has_analysis, find_missing_analyses, find_recent_failures`

---

## Phase 3: Utilities (TDD)

### Task 3.1: Implement logging.py

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_logging.py`):
```python
import pytest
import json

def test_logger_outputs_json_format(capsys):
    """Logger should output JSON formatted logs"""
    from src.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("test_event", key="value")

    captured = capsys.readouterr()
    log_entry = json.loads(captured.out.strip())
    assert "event" in log_entry
    assert log_entry["key"] == "value"

def test_logger_includes_correlation_id(capsys):
    """Logger should include correlation_id when provided"""
    from src.utils.logging import get_logger, bind_correlation_id

    logger = get_logger(__name__)
    bind_correlation_id("test-corr-123")
    logger.info("test_event")

    captured = capsys.readouterr()
    log_entry = json.loads(captured.out.strip())
    assert log_entry.get("correlation_id") == "test-corr-123"
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/utils/logging.py`):
```python
import structlog
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')

def bind_correlation_id(correlation_id: str):
    """Bind correlation_id to current context"""
    correlation_id_var.set(correlation_id)

def add_correlation_id(logger, method_name, event_dict):
    """Add correlation_id to log events"""
    corr_id = correlation_id_var.get()
    if corr_id:
        event_dict['correlation_id'] = corr_id
    return event_dict

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
)

def get_logger(name: str):
    """Get configured structlog logger"""
    return structlog.get_logger(name)
```

4. **確認測試通過**

5. **Git commit**: `📋 [FEAT] Implement structlog JSON logging configuration`

---

### Task 3.2: Implement sanitizer.py

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_sanitizer.py`):
```python
import pytest

def test_sanitize_content_removes_script_tags():
    """sanitize_content should remove script tags"""
    from src.utils.sanitizer import sanitize_content

    html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
    result = sanitize_content(html)

    assert "script" not in result.lower()
    assert "Hello" in result
    assert "World" in result

def test_sanitize_content_removes_style_tags():
    """sanitize_content should remove style tags"""
    from src.utils.sanitizer import sanitize_content

    html = "<p>Hello</p><style>.hidden{display:none}</style>"
    result = sanitize_content(html)

    assert "style" not in result.lower()

def test_sanitize_content_truncates_long_content():
    """sanitize_content should truncate content exceeding MAX_LENGTH"""
    from src.utils.sanitizer import sanitize_content, MAX_CONTENT_LENGTH

    html = "<p>" + "a" * 60000 + "</p>"
    result = sanitize_content(html)

    assert len(result) <= MAX_CONTENT_LENGTH + 20
    assert "[Content truncated]" in result

def test_sanitize_content_preserves_paragraph_structure():
    """sanitize_content should preserve paragraph breaks"""
    from src.utils.sanitizer import sanitize_content

    html = "<p>Para 1</p><p>Para 2</p>"
    result = sanitize_content(html)

    assert "\n" in result
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/utils/sanitizer.py`):
```python
from bs4 import BeautifulSoup

MAX_CONTENT_LENGTH = 50_000

def sanitize_content(raw_html: str) -> str:
    """Convert HTML to plain text and sanitize"""
    soup = BeautifulSoup(raw_html, 'html.parser')

    for tag in soup(['script', 'style', 'nav', 'footer', 'aside']):
        tag.decompose()

    text = soup.get_text(separator='\n', strip=True)

    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH] + "\n[Content truncated]"

    return text
```

4. **確認測試通過**

5. **Git commit**: `🧹 [FEAT] Implement sanitize_content with HTML removal and truncation`

---

### Task 3.3: Implement URL hash generation

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_sanitizer.py` 新增):
```python
def test_generate_url_hash_returns_sha256():
    """generate_url_hash should return SHA-256 hash"""
    from src.utils.sanitizer import generate_url_hash

    url = "https://example.com/article/123"
    result = generate_url_hash(url)

    assert len(result) == 64  # SHA-256 hex length
    assert result.isalnum()

def test_generate_url_hash_is_deterministic():
    """Same URL should produce same hash"""
    from src.utils.sanitizer import generate_url_hash

    url = "https://example.com/article/123"
    assert generate_url_hash(url) == generate_url_hash(url)

def test_generate_url_hash_different_urls():
    """Different URLs should produce different hashes"""
    from src.utils.sanitizer import generate_url_hash

    hash1 = generate_url_hash("https://example.com/1")
    hash2 = generate_url_hash("https://example.com/2")
    assert hash1 != hash2
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/utils/sanitizer.py` 新增):
```python
import hashlib

def generate_url_hash(url: str) -> str:
    """Generate SHA-256 hash of URL"""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()
```

4. **確認測試通過**

5. **Git commit**: `🔐 [FEAT] Implement URL hash generation with SHA-256`

---

### Task 3.4 & 3.5: 已在上述步驟中完成

**Git commit**: `✅ [TEST] Add comprehensive unit tests for utilities`

---

## Phase 4: RSS Scraper (TDD)

### Task 4.1: Create BaseScraper abstract class

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_scrapers.py`):
```python
import pytest

def test_base_scraper_is_abstract():
    """BaseScraper should be abstract"""
    from src.scrapers.base import BaseScraper

    with pytest.raises(TypeError):
        BaseScraper()

def test_base_scraper_requires_scrape_method():
    """Subclass must implement scrape()"""
    from src.scrapers.base import BaseScraper

    class IncompleteScraper(BaseScraper):
        pass

    with pytest.raises(TypeError):
        IncompleteScraper()
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/scrapers/base.py`):
```python
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

@dataclass
class ScrapedArticle:
    url: str
    title: str
    content: str
    published_at: str
    source: str
    metadata: dict = None

class BaseScraper(ABC):
    @abstractmethod
    def scrape(self) -> List[ScrapedArticle]:
        pass
```

4. **確認測試通過**

5. **Git commit**: `🏗️ [FEAT] Create BaseScraper abstract class`

---

### Task 4.2 - 4.6: Implement RssScraper

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_rss_scraper.py`):
```python
import pytest
import responses

@responses.activate
def test_rss_scraper_parses_feed():
    """RssScraper should parse RSS feed entries"""
    from src.scrapers.rss_scraper import RssScraper

    rss_content = '''<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Digital Twins Article</title>
          <link>https://example.com/article</link>
          <description>Content about digital twins</description>
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

    assert len(articles) == 1
    assert articles[0].title == "Digital Twins Article"

def test_rss_scraper_filters_by_keywords():
    """RssScraper should filter by Digital Twins keywords"""
    from src.scrapers.rss_scraper import RssScraper

    # Test keyword matching logic
    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("Digital Twins in Manufacturing")
    assert scraper._matches_keywords("The rise of digital twin technology")
    assert not scraper._matches_keywords("Unrelated article about cats")

@responses.activate
def test_rss_scraper_handles_feed_error():
    """RssScraper should handle feed errors gracefully"""
    from src.scrapers.rss_scraper import RssScraper

    responses.add(
        responses.GET,
        "https://example.com/feed",
        status=500
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []  # Returns empty list on error
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/scrapers/rss_scraper.py`):
```python
import feedparser
import requests
import time
import re
from typing import List, Optional
from src.scrapers.base import BaseScraper, ScrapedArticle
from src.utils.sanitizer import sanitize_content
from src.utils.logging import get_logger

logger = get_logger(__name__)

DIGITAL_TWINS_KEYWORDS = [
    r'digital\s+twin',
    r'digital\s+twins',
    r'twin\s+technology',
]

class RssScraper(BaseScraper):
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
        return bool(self._keyword_pattern.search(text))

    def scrape(self) -> List[ScrapedArticle]:
        """Scrape RSS feed for Digital Twins articles"""
        try:
            response = requests.get(self.url, timeout=30, headers={
                'User-Agent': 'Digital-Twins-Scraper/1.0'
            })
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

            time.sleep(self.rate_limit)

        return articles
```

4. **確認測試通過**

5. **Git commit**: `📰 [FEAT] Implement RssScraper with feed parsing and keyword filtering`

---

### Task 4.7: Configure RSS sources

**更動檔案**: `src/config.py`

**內容** (新增):
```python
RSS_SOURCES = [
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
```

**Git commit**: `⚙️ [FEAT] Configure RSS sources (TechCrunch, VentureBeat, IoT World Today)`

---

### Task 4.8 & 4.9: Unit tests for RSS

**Git commit**: `✅ [TEST] Add comprehensive unit tests for RSS scraper`

---

## Phase 5: arXiv API Scraper (TDD)

### Task 5.1 - 5.5: Implement ArxivScraper

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_arxiv_scraper.py`):
```python
import pytest
import responses

def test_arxiv_scraper_builds_query():
    """ArxivScraper should build correct search query"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper()
    query = scraper._build_query()

    assert "digital" in query.lower()
    assert "twin" in query.lower()

@responses.activate
def test_arxiv_scraper_extracts_metadata():
    """ArxivScraper should extract paper metadata"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    # Mock arXiv API response (Atom format)
    atom_response = '''<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Digital Twins in Manufacturing</title>
        <summary>Abstract about digital twins...</summary>
        <published>2024-01-01T00:00:00Z</published>
        <author><name>John Doe</name></author>
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
    assert "Digital Twins" in articles[0].title

def test_arxiv_scraper_limits_results():
    """ArxivScraper should limit to 100 results"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper(max_results=100)
    assert scraper.max_results == 100
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/scrapers/arxiv_scraper.py`)

4. **確認測試通過**

5. **Git commit**: `📚 [FEAT] Implement ArxivScraper with API query and metadata extraction`

---

### Task 5.6: Unit tests

**Git commit**: `✅ [TEST] Add unit tests for arXiv API response parsing`

---

## Phase 6: Blog Scraper (TDD)

### Task 6.1 - 6.5: Implement BlogScraper

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_blog_scraper.py`):
```python
import pytest
import responses

def test_blog_scraper_discovers_article_links():
    """BlogScraper should discover article links from listing"""
    from src.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <div class="post">
        <a href="/blog/digital-twins-article">Article 1</a>
      </div>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com",
        source="test",
        selectors={'article_link': '.post a'}
    )

    links = scraper._extract_links(html)
    assert len(links) == 1
    assert "/blog/digital-twins-article" in links[0]

def test_blog_scraper_extracts_content():
    """BlogScraper should extract content with CSS selectors"""
    from src.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <article>
        <h1>Article Title</h1>
        <div class="content">Article content here</div>
      </article>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com",
        source="test",
        selectors={
            'title': 'h1',
            'content': '.content'
        }
    )

    title, content = scraper._extract_article(html)
    assert title == "Article Title"
    assert "Article content" in content
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/scrapers/blog_scraper.py`)

4. **確認測試通過**

5. **Git commit**: `📝 [FEAT] Implement BlogScraper with CSS selectors`

---

### Task 6.6 & 6.7: Configure and test

**Git commit**: `⚙️ [FEAT] Configure blog sources (NVIDIA, Siemens, AWS, Azure)`
**Git commit**: `✅ [TEST] Add unit tests for blog parsing with mock HTML`

---

## Phase 7: LLM Analyzer (TDD)

### Task 7.1 & 7.2: LLMProvider and AnalysisResult

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_llm_analyzer.py`):
```python
import pytest

def test_llm_provider_is_abstract():
    """LLMProvider should be abstract"""
    from src.analyzers.llm_provider import LLMProvider

    with pytest.raises(TypeError):
        LLMProvider()

def test_analysis_result_has_required_fields():
    """AnalysisResult should have all fields"""
    from src.analyzers.llm_provider import AnalysisResult

    result = AnalysisResult(
        tags=["tag1"],
        pain_points="pain",
        insights="insight",
        innovations="innovation",
        input_tokens=100,
        output_tokens=50
    )

    assert result.tags == ["tag1"]
    assert result.input_tokens == 100
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/analyzers/llm_provider.py`):
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

@dataclass
class AnalysisResult:
    tags: List[str]
    pain_points: str
    insights: str
    innovations: str
    input_tokens: int
    output_tokens: int

class LLMProvider(ABC):
    @abstractmethod
    def analyze(self, content: str, prompt: str) -> AnalysisResult:
        pass
```

4. **確認測試通過**

5. **Git commit**: `🤖 [FEAT] Create LLMProvider abstract class and AnalysisResult dataclass`

---

### Task 7.3 - 7.7: Implement ClaudeProvider

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_claude_provider.py`):
```python
import pytest
from unittest.mock import Mock, patch

def test_claude_provider_calls_api():
    """ClaudeProvider should call Anthropic API"""
    from src.analyzers.claude import ClaudeProvider

    with patch('src.analyzers.claude.anthropic.Anthropic') as mock_client:
        mock_response = Mock()
        mock_response.content = [Mock(text='{"tags":["tag1"],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.return_value.messages.create.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test content", "test prompt")

        assert result.tags == ["tag1"]
        assert result.input_tokens == 100

def test_claude_provider_retries_on_error():
    """ClaudeProvider should retry on API errors"""
    from src.analyzers.claude import ClaudeProvider

    with patch('src.analyzers.claude.anthropic.Anthropic') as mock_client:
        # First call fails, second succeeds
        mock_response = Mock()
        mock_response.content = [Mock(text='{"tags":[],"pain_points":"","insights":"","innovations":""}')]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client.return_value.messages.create.side_effect = [
            Exception("API Error"),
            mock_response
        ]

        provider = ClaudeProvider(api_key="test-key")
        result = provider.analyze("test", "prompt")

        assert mock_client.return_value.messages.create.call_count == 2
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/analyzers/claude.py`):
```python
import anthropic
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from src.analyzers.llm_provider import LLMProvider, AnalysisResult
from src.utils.logging import get_logger

logger = get_logger(__name__)

class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    def analyze(self, content: str, prompt: str) -> AnalysisResult:
        """Analyze content using Claude API"""
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": full_prompt}]
        )

        result_json = json.loads(response.content[0].text)

        return AnalysisResult(
            tags=result_json.get('tags', []),
            pain_points=result_json.get('pain_points', ''),
            insights=result_json.get('insights', ''),
            innovations=result_json.get('innovations', ''),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
```

4. **確認測試通過**

5. **Git commit**: `🧠 [FEAT] Implement ClaudeProvider with retry logic and token tracking`

---

### Task 7.4: Create prompt template

**更動檔案**: `src/prompts/analysis.txt`

**內容**:
```
You are a professional technology analyst specializing in Digital Twins technology.

Analyze the following article and extract:
1. **tags**: A list of relevant keywords/topics (3-7 tags)
2. **pain_points**: Key challenges or problems mentioned
3. **insights**: Important observations or trends
4. **innovations**: New technologies, methods, or solutions mentioned

Return your analysis as valid JSON with these exact fields:
{
  "tags": ["tag1", "tag2", ...],
  "pain_points": "description of pain points",
  "insights": "key insights from the article",
  "innovations": "innovations mentioned"
}

Only output the JSON, no other text.
```

**Git commit**: `📄 [FEAT] Create analysis prompt template`

---

### Task 7.8: Unit tests

**Git commit**: `✅ [TEST] Add unit tests for LLM analyzer with mocked responses`

---

## Phase 8: Main Execution Flow (TDD)

### Task 8.1: CLI entry point

**TDD 步驟**:

1. **寫測試** (`tests/unit/test_main.py`):
```python
import pytest
from unittest.mock import patch

def test_main_accepts_daily_argument():
    """main should accept 'daily' as argument"""
    from src.main import parse_args

    args = parse_args(['daily'])
    assert args.command == 'daily'

def test_main_accepts_weekly_argument():
    """main should accept 'weekly' as argument"""
    from src.main import parse_args

    args = parse_args(['weekly'])
    assert args.command == 'weekly'

def test_main_accepts_remediate_argument():
    """main should accept 'remediate' as argument"""
    from src.main import parse_args

    args = parse_args(['remediate'])
    assert args.command == 'remediate'
```

2. **確認測試失敗**

3. **寫最精簡實作** (`src/main.py`):
```python
import argparse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from src.utils.logging import get_logger, bind_correlation_id
from src.config import get_sources
from src.database import get_session, has_analysis, find_recent_failures

logger = get_logger(__name__)

MAX_WORKERS = 3
MAX_EXECUTION_TIME = 50 * 60  # 50 minutes
BATCH_SIZE = 50

def parse_args(args=None):
    parser = argparse.ArgumentParser(description='Digital Twins Scraper')
    parser.add_argument('command', choices=['daily', 'weekly', 'remediate'])
    return parser.parse_args(args)

def main():
    args = parse_args()
    correlation_id = str(uuid.uuid4())
    bind_correlation_id(correlation_id)

    logger.info("execution_started", command=args.command)

    if args.command == 'daily':
        run_daily_scrape()
    elif args.command == 'weekly':
        run_weekly_scrape()
    elif args.command == 'remediate':
        run_remediate()

if __name__ == '__main__':
    main()
```

4. **確認測試通過**

5. **Git commit**: `🚀 [FEAT] Implement CLI entry point with argparse`

---

### Task 8.2 - 8.10: Implement execution functions

**依序實作並 commit**:

- `🔄 [FEAT] Implement run_daily_scrape with ThreadPoolExecutor`
- `📅 [FEAT] Implement run_weekly_scrape function`
- `🔁 [FEAT] Implement auto_redrive_recent_failures function`
- `💾 [FEAT] Implement process_article with transaction handling`
- `🛡️ [FEAT] Implement process_article_safe with error recording`
- `📦 [FEAT] Implement batch size limiting (max 50 articles)`
- `⏰ [FEAT] Implement execution timeout (50 minutes)`
- `🛑 [FEAT] Implement graceful shutdown on timeout`
- `🔗 [FEAT] Implement correlation_id generation and propagation`

---

## Phase 9-13: 剩餘實作

依照相同 TDD 模式實作：

### Phase 9: Error Handling
- `❌ [FEAT] Implement record_failure function`
- `🔧 [FEAT] Implement remediate command`
- `👻 [FEAT] Implement scan_missing_analyses`
- `✅ [TEST] Add integration tests for failure recording`
- `✅ [TEST] Add integration tests for auto-redrive`

### Phase 10: Configuration
- `⚙️ [FEAT] Implement config.py with environment variable loading`
- `📋 [FEAT] Define source configurations`
- `🔀 [FEAT] Implement source loading by schedule_type`
- `✅ [FEAT] Add configuration validation at startup`

### Phase 11: Integration Testing
- `🐳 [TEST] Add docker-compose.yml for local PostgreSQL`
- `✅ [TEST] Add integration test for full scrape-analyze flow`
- `✅ [TEST] Add integration test for transaction atomicity`
- `✅ [TEST] Add integration test for deduplication`
- `✅ [TEST] Add integration test for connection cleanup`

### Phase 12: Observability
- `📋 [FEAT] Configure structlog with JSON output`
- `🔗 [FEAT] Add correlation_id to all log entries`
- `📊 [FEAT] Add execution summary logging`
- `📈 [FEAT] Add LLM metrics logging`
- `🚨 [FEAT] Add optional Sentry integration`

### Phase 13: Deployment
- `🧪 [TEST] Verify Docker build locally`
- `🚂 [DOCS] Document Railway project setup`
- `🗄️ [DOCS] Document PostgreSQL database setup`
- `🔐 [DOCS] Document environment variables`
- `⏰ [FEAT] Create daily-scraper Cron Job configuration`
- `📅 [FEAT] Create weekly-scraper Cron Job configuration`
- `🔄 [DOCS] Document database migration procedure`
- `✅ [DOCS] Document verification steps`
- `📊 [DOCS] Document Grafana Cloud setup`

---

## 執行順序摘要

| Phase | Tasks | 預估 Commits |
|-------|-------|-------------|
| 1. Project Setup | 1.1 - 1.6 | 6 |
| 2. Database Layer | 2.1 - 2.7 | 7 |
| 3. Utilities | 3.1 - 3.5 | 4 |
| 4. RSS Scraper | 4.1 - 4.9 | 4 |
| 5. arXiv Scraper | 5.1 - 5.6 | 2 |
| 6. Blog Scraper | 6.1 - 6.7 | 3 |
| 7. LLM Analyzer | 7.1 - 7.8 | 4 |
| 8. Main Flow | 8.1 - 8.10 | 10 |
| 9. Error Handling | 9.1 - 9.5 | 5 |
| 10. Configuration | 10.1 - 10.4 | 4 |
| 11. Integration Tests | 11.1 - 11.5 | 5 |
| 12. Observability | 12.1 - 12.5 | 5 |
| 13. Deployment | 13.1 - 13.9 | 9 |

**總計**: ~68 commits

---

## 驗證命令

```bash
# 執行所有單元測試
pytest tests/unit -v --cov=src --cov-fail-under=80

# 執行整合測試
docker-compose up -d postgres
pytest tests/integration -v
docker-compose down

# 本地 Docker 測試
docker build -t digital-twins-scraper .
docker run --env-file .env digital-twins-scraper python -m src.main daily
```
