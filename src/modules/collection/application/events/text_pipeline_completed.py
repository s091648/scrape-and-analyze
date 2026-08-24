from dataclasses import dataclass, field
from typing import List, Tuple

from src.modules.collection.application.use_cases import SourceStats
from src.shared.domain.value_objects.job_execution_meta import JobExecutionMeta


@dataclass(frozen=True)
class TextPipelineCompletedEvent:
    """024-async-pipeline-refactor: published once every article's text stage
    (scrape+analyze+translate) has settled — succeeded or permanently failed,
    never waiting on RAG ingestion (spec.md FR-004/FR-005). Triggers the
    search-index rebuild and cache invalidation/warmup, which only depend on
    article/analysis text content, not RAG vectors. PipelineCompletedEvent
    (the "everything including RAG" signal) is unchanged and still fires
    separately, later — see collection_pipeline.py's two-barrier `run()`."""
    stats: List[SourceStats]
    execution: JobExecutionMeta
    rate_limited_hosts: Tuple[str, ...] = field(default_factory=tuple)
    rate_limited_llm_providers: Tuple[str, ...] = field(default_factory=tuple)
