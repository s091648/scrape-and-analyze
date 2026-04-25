from enum import Enum


class ArticleOutcome(Enum):
    NEW = "new"
    DUPLICATE = "duplicate"
    FAILED = "failed"