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
SERVICE_NAME_BACKEND = "scrape-analyzer-backend"


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
    BACKEND = "backend"


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
    PIPELINE_DISCOVER = "pipeline.discover"
    DISCOVER_TASK = "discover.task"
    PIPELINE_FETCH = "pipeline.fetch"
    ARTICLE_PIPELINE = "article.pipeline"
    ARTICLE_SCRAPED_HANDLE = "article.scraped.handle"
    ARTICLE_PROCESSED_HANDLE = "article.processed.handle"
    TAG_NORMALIZATION_HANDLE = "article.tag_normalization.handle"
    ANALYSIS_COMPLETED_HANDLE = "article.analysis_completed.handle"
    ARTICLE_TRANSLATE_HANDLE = "article.translate.handle"
    ARTICLE_RAG_INGEST = "article.rag_ingest"
    # Generic wrapper span every *FailedEvent goes through (FailedTaskPersistenceHandler),
    # so the OTel ERROR status lands on this child span instead of bleeding onto the
    # parent article.pipeline — that keeps "article.pipeline is ERROR" meaning a hard
    # failure (couldn't even run the pipeline) vs. a partial/downstream-stage failure.
    FAILED_TASK_HANDLE = "article.failed_task.handle"
    ANALYSIS_FAILED_HANDLE = "article.analysis_failed.handle"
    TAG_NORMALIZATION_FAILED_HANDLE = "article.tag_normalization_failed.handle"
    TRANSLATION_FAILED_HANDLE = "article.translation_failed.handle"
    RAG_INGESTION_FAILED_HANDLE = "rag.ingestion_failed.handle"
    RAG_CONFIG_FAILED_HANDLE = "rag.config_failed.handle"
    PIPELINE_COMPLETED_METRICS_HANDLE = "scraper.pipeline_completed.metrics_handle"
    PIPELINE_COMPLETED_NOTIFY = "scraper.pipeline_completed.notify"
    CACHE_INVALIDATION_HANDLE = "cache.invalidation.handle"
    CACHE_WARMUP_HANDLE = "cache.warmup.handle"
    SEARCH_INDEX_REBUILD_HANDLE = "search.index_rebuild.handle"
    WEEKLY_REPORT_RUN = "weekly_report.run"
    WEEKLY_REPORT_TOPIC = "weekly_report.topic"
    WEEKLY_REPORT_SUMMARIZE = "weekly_report.summarize"
    WEEKLY_REPORT_IMAGE = "weekly_report.image"
    WEEKLY_REPORT_TRANSLATE = "weekly_report.translate"
    WEEKLY_REPORT_NOTIFY = "weekly_report.notify"
    REFRESH_METRICS_RUN = "refresh_metrics.run"
    DEDUP_RECONCILE_RUN = "dedup_reconcile.run"
    RAG_BACKFILL_RUN = "rag_backfill.run"


# ── Span attributes ──────────────────────────────────────────────────────────

class SpanAttribute(StrEnum):
    RUN_ID = "run.id"
    CORRELATION_ID = "run.correlation_id"


# ── Tempo TraceQL resource label ─────────────────────────────────────────────

class TraceQLResource(StrEnum):
    SERVICE_NAME = "resource.service.name"
    DEPLOYMENT_ENVIRONMENT = "resource.deployment.environment"
