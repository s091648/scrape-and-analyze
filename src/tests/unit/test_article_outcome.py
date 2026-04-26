def test_article_outcome_values():
    from src.modules.collection.application.use_cases import ArticleOutcome
    assert ArticleOutcome.NEW.value == "new"
    assert ArticleOutcome.DUPLICATE.value == "duplicate"
    assert ArticleOutcome.FAILED.value == "failed"


def test_article_outcome_is_not_bool():
    from src.modules.collection.application.use_cases import ArticleOutcome
    assert ArticleOutcome.NEW is not True
    assert ArticleOutcome.FAILED is not False