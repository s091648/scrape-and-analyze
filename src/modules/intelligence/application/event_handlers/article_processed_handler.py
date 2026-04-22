from src.shared.application.events import ArticleProcessedEvent
from src.modules.intelligence.application.use_cases import AnalyzeArticleUseCase


class ArticleProcessedHandler:
    def __init__(self, use_case: AnalyzeArticleUseCase) -> None:
        self._use_case = use_case

    def handle(self, event: ArticleProcessedEvent) -> bool:
        return self._use_case.execute(event.article)
