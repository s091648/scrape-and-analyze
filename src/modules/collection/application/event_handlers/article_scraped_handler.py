from src.modules.collection.application.events import ArticleScrapedEvent
from src.modules.collection.application.use_cases import ProcessScrapedArticleUseCase


class ArticleScrapedHandler:
    def __init__(self, use_case: ProcessScrapedArticleUseCase) -> None:
        self._use_case = use_case

    def handle(self, event: ArticleScrapedEvent) -> None:
        self._use_case.execute(event)
