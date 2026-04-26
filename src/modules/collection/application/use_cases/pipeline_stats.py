import threading
from dataclasses import dataclass
from typing import List

from .article_outcome import ArticleOutcome


@dataclass
class SourceStats:
    source: str
    new: int = 0
    duplicate: int = 0
    failed: int = 0


class PipelineStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sources: dict[str, SourceStats] = {}

    def record(self, source: str, outcome: ArticleOutcome) -> None:
        with self._lock:
            if source not in self._sources:
                self._sources[source] = SourceStats(source=source)
            s = self._sources[source]
            if outcome == ArticleOutcome.NEW:
                s.new += 1
            elif outcome in (ArticleOutcome.DUPLICATE, ArticleOutcome.DUPLICATE_NEEDS_ANALYSIS):
                s.duplicate += 1
            else:
                s.failed += 1

    def get_results(self) -> List[SourceStats]:
        with self._lock:
            return list(self._sources.values())