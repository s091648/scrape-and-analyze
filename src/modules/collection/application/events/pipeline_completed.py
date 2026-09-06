from dataclasses import dataclass, field
from typing import List, Tuple

from src.modules.collection.application.use_cases import SourceStats
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


@dataclass(frozen=True)
class PipelineCompletedEvent:
    """Event published when the full scrape pipeline finishes, carrying per-source stats and execution metadata."""
    stats: List[SourceStats]
    execution: JobExecutionMeta
    # Two separate ID spaces, deliberately not merged: ScrapeExecutor tracks HTTP
    # hostnames (e.g. "export.arxiv.org"), ResilientLLMService tracks provider_name
    # (e.g. "gemini") — there's no shared namespace between "which scrape source got
    # rate-limited" and "which LLM provider got rate-limited" to unify them into.
    rate_limited_hosts: Tuple[str, ...] = field(default_factory=tuple)
    rate_limited_llm_providers: Tuple[str, ...] = field(default_factory=tuple)
    # Articles that were saved (counted in stats as `new`) but had a later stage
    # — analysis / tag normalization / translation / RAG ingestion — fail. Kept
    # separate from SourceStats.failed, which only ever counts scrape/save-stage
    # failures.
    partial_failure_count: int = 0
    # Articles whose RAG ingestion was skipped without being attempted because
    # the embedding provider's daily request cap (RPD) was already spent this
    # run — the circuit breaker in CollectionPipeline stops dispatching RAG once
    # the first RateLimitExhausted is seen. These keep has_vectors=FALSE and are
    # left for the RAG-backfill cron. (Subset of the FailedTask rows written at
    # run end; timeouts are recorded there too but not counted here.)
    rag_rate_limited_skipped: int = 0
