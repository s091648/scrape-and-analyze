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
