from abc import ABC, abstractmethod
from src.infrastructure.shared.observability import RunSummary


class BaseNotifier(ABC):
    @abstractmethod
    def send_scrape_summary(self, summary: RunSummary, duration: float) -> None: ...
