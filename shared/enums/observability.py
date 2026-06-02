"""
Centralized observability constants for scrape-analyzer.

Used by:
  - src/ (OTel metrics, tracing, Loki logging)
  - backend/ (Grafana API router)

TypeScript mirror: frontend/lib/observability-constants.ts
"""

from enum import StrEnum


# ── Service identity ──────────────────────────────────────────────────────────

SERVICE_NAME = "scrape-analyzer"


# ── OTel Resource ────────────────────────────────────────────────────────────

class ResourceLabel(StrEnum):
    SERVICE_NAME = "service.name"
    DEPLOYMENT_ENVIRONMENT = "deployment.environment"


# ── Metric names ─────────────────────────────────────────────────────────────

class MetricName(StrEnum):
    RUNS_TOTAL = "scraper_runs_total"
    RUN_DURATION_SECONDS = "scraper_run_duration_seconds"
    ARTICLES_FOUND_TOTAL = "scraper_articles_found_total"
    ARTICLES_NEW_TOTAL = "scraper_articles_new_total"
    ARTICLES_DUPLICATE_TOTAL = "scraper_articles_duplicate_total"
    ERRORS_TOTAL = "scraper_errors_total"


# ── Metric label keys & values ───────────────────────────────────────────────

class MetricLabelKey(StrEnum):
    SOURCE = "source"


class MetricSourceValue(StrEnum):
    ARXIV = "arxiv"
    RSS = "rss"
    BLOG = "blog"


# ── Loki labels (stream selectors — indexed) ────────────────────────────────

class LokiLabel(StrEnum):
    APP = "app"
    ENV = "env"


class LokiAppValue(StrEnum):
    SCRAPER = "scraper"


class LokiEnvValue(StrEnum):
    LOCAL = "local"
    PRODUCTION = "production"


# ── Loki log fields (extracted via | json, NOT indexed) ─────────────────────

class LogField(StrEnum):
    LEVEL = "level"
    EVENT = "event"
    CORRELATION_ID = "correlation_id"
    TOPIC_ID = "topic_id"


class LogLevel(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ── Span names ───────────────────────────────────────────────────────────────

class SpanName(StrEnum):
    SCRAPER_RUN = "scraper.run"
    ARTICLE_PIPELINE = "article.pipeline"
    ARTICLE_SCRAPED_HANDLE = "article.scraped.handle"
    ARTICLE_PROCESSED_HANDLE = "article.processed.handle"
    TAG_NORMALIZATION_HANDLE = "article.tag_normalization.handle"
    ANALYSIS_COMPLETED_HANDLE = "article.analysis_completed.handle"
    ARTICLE_TRANSLATE_HANDLE = "article.translate.handle"
    ANALYSIS_FAILED_HANDLE = "article.analysis_failed.handle"
    TAG_NORMALIZATION_FAILED_HANDLE = "article.tag_normalization_failed.handle"
    TRANSLATION_FAILED_HANDLE = "article.translation_failed.handle"
    PIPELINE_COMPLETED_HANDLE = "scraper.pipeline_completed.handle"
    PIPELINE_COMPLETED_NOTIFY = "scraper.pipeline_completed.notify"


# ── Span attributes ──────────────────────────────────────────────────────────

class SpanAttribute(StrEnum):
    RUN_ID = "run.id"
    CORRELATION_ID = "run.correlation_id"


# ── Tempo TraceQL resource label ─────────────────────────────────────────────

class TraceQLResource(StrEnum):
    SERVICE_NAME = "resource.service.name"
    DEPLOYMENT_ENVIRONMENT = "resource.deployment.environment"
