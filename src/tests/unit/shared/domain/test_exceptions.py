import pytest


def test_shared_categories_subclass_domain_error():
    from src.shared.domain.exceptions import (
        DomainError,
        ValidationError,
        NotFoundError,
        ConflictError,
        UnauthorizedError,
        ForbiddenError,
        ExternalDependencyError,
    )

    for category in (
        ValidationError,
        NotFoundError,
        ConflictError,
        UnauthorizedError,
        ForbiddenError,
        ExternalDependencyError,
    ):
        assert issubclass(category, DomainError)


@pytest.mark.parametrize(
    "leaf_name",
    [
        "InvalidUrlHashError",
        "InvalidScraperKeywordTypeError",
        "UnsupportedSourceTypeError",
        "InvalidScraperIntervalError",
    ],
)
def test_collection_validation_leaves_are_validation_and_context_errors(leaf_name):
    from src.modules.collection.domain import exceptions as collection_exceptions
    from src.modules.collection.domain.exceptions import CollectionDomainError
    from src.shared.domain.exceptions import ValidationError

    leaf = getattr(collection_exceptions, leaf_name)
    instance = leaf.__new__(leaf)
    assert isinstance(instance, ValidationError)
    assert isinstance(instance, CollectionDomainError)


@pytest.mark.parametrize(
    "leaf_name",
    [
        "InvalidSuggestionStatusError",
        "InvalidSimilarityScoreError",
        "InvalidWeeklyReportStatusError",
    ],
)
def test_intelligence_validation_leaves_are_validation_and_context_errors(leaf_name):
    from src.modules.intelligence.domain import exceptions as intelligence_exceptions
    from src.modules.intelligence.domain.exceptions import IntelligenceDomainError
    from src.shared.domain.exceptions import ValidationError

    leaf = getattr(intelligence_exceptions, leaf_name)
    instance = leaf.__new__(leaf)
    assert isinstance(instance, ValidationError)
    assert isinstance(instance, IntelligenceDomainError)
