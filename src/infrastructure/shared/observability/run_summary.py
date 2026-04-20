"""
RunSummary — thread-safe per-source stats aggregator for one scraper run.
Pure Python, no infrastructure dependency.
"""
import threading
from dataclasses import dataclass
from typing import List


@dataclass
class SourceResult:
    source: str
    new: int = 0
    duplicate: int = 0
    failed: int = 0


class RunSummary:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sources: dict[str, SourceResult] = {}

    def _get(self, source: str) -> SourceResult:
        if source not in self._sources:
            self._sources[source] = SourceResult(source=source)
        return self._sources[source]

    def record_new(self, source: str, count: int = 1) -> None:
        with self._lock:
            self._get(source).new += count

    def record_duplicate(self, source: str, count: int = 1) -> None:
        with self._lock:
            self._get(source).duplicate += count

    def record_failed(self, source: str, count: int = 1) -> None:
        with self._lock:
            self._get(source).failed += count

    def get_results(self) -> List[SourceResult]:
        with self._lock:
            return list(self._sources.values())

    def total_new(self) -> int:
        return sum(r.new for r in self.get_results())

    def total_duplicate(self) -> int:
        return sum(r.duplicate for r in self.get_results())

    def total_failed(self) -> int:
        return sum(r.failed for r in self.get_results())
