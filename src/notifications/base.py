from abc import ABC, abstractmethod
from src.observability.run_summary import RunSummary


class BaseNotifier(ABC):
    @abstractmethod
    def send_scrape_summary(self, summary: RunSummary, duration: float) -> None: ...
