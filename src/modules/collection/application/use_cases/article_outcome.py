from enum import Enum


class ArticleOutcome(Enum):
    NEW = "new"
    DUPLICATE = "duplicate"
    DUPLICATE_NEEDS_ANALYSIS = "duplicate_needs_analysis"
    FAILED = "failed"