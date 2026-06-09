from enum import Enum


class ArticleOutcome(Enum):
    """Enum representing the result of processing a scraped article (new, duplicate, or failed)."""
    NEW = "new"
    DUPLICATE = "duplicate"
    DUPLICATE_NEEDS_ANALYSIS = "duplicate_needs_analysis"
    FAILED = "failed"