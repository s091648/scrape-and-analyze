"""Unit tests for SqlAlchemySearchTermRepository (023-article-search follow-up) — the
ORM implementation that replaced shared/search_index/'s raw-SQL repo once query-time
evidence showed backend/services/search_service.py needed a term->article lookup.
Mocked session — real INSERT/DELETE/FK behavior is covered by the integration test in
backend/tests/integration/test_search.py (which seeds via this same ORM shape)."""
import uuid
from unittest.mock import MagicMock

import pytest

from src.infrastructure.persistence.intelligence.search_term_repo_impl import SqlAlchemySearchTermRepository


@pytest.fixture
def session():
    return MagicMock()


@pytest.fixture
def repo(session):
    return SqlAlchemySearchTermRepository(session)


def test_replace_all_deletes_existing_rows_before_inserting(repo, session):
    topic_id = uuid.uuid4()
    article_id = uuid.uuid4()

    repo.replace_all({(topic_id, "learning", "en"): {article_id}})

    # SearchTermArticle deleted before SearchTerm (children before parents).
    assert session.query.return_value.delete.call_count == 2


def test_replace_all_writes_search_term_with_occurrence_count_as_article_set_size(repo, session):
    topic_id = uuid.uuid4()
    a, b = uuid.uuid4(), uuid.uuid4()

    repo.replace_all({(topic_id, "learning", "en"): {a, b}})

    search_terms = session.add_all.call_args_list[0].args[0]
    assert len(search_terms) == 1
    term = search_terms[0]
    assert term.topic_id == topic_id
    assert term.term == "learning"
    assert term.language == "en"
    assert term.occurrence_count == 2


def test_replace_all_writes_one_search_term_article_row_per_article_id(repo, session):
    topic_id = uuid.uuid4()
    a, b = uuid.uuid4(), uuid.uuid4()

    repo.replace_all({(topic_id, "learning", "en"): {a, b}})

    search_term_articles = session.add_all.call_args_list[1].args[0]
    assert {row.article_id for row in search_term_articles} == {a, b}
    assert len({row.search_term_id for row in search_term_articles}) == 1  # both link to the same SearchTerm


def test_replace_all_links_search_term_article_to_correct_search_term_id(repo, session):
    topic_id = uuid.uuid4()
    a = uuid.uuid4()

    repo.replace_all({(topic_id, "learning", "en"): {a}})

    search_terms = session.add_all.call_args_list[0].args[0]
    search_term_articles = session.add_all.call_args_list[1].args[0]
    assert search_term_articles[0].search_term_id == search_terms[0].id


def test_replace_all_skips_empty_article_sets():
    """Defensive guard — the use case shouldn't ever produce an empty set for a key that
    exists at all, but replace_all must not write an orphaned, uncountable term if it does."""
    session = MagicMock()
    repo = SqlAlchemySearchTermRepository(session)
    topic_id = uuid.uuid4()

    repo.replace_all({(topic_id, "orphaned", "en"): set()})

    search_terms = session.add_all.call_args_list[0].args[0]
    assert search_terms == []


def test_replace_all_commits(repo, session):
    topic_id = uuid.uuid4()

    repo.replace_all({(topic_id, "learning", "en"): {uuid.uuid4()}})

    session.commit.assert_called_once()


def test_replace_all_rolls_back_on_commit_failure(repo, session):
    session.commit.side_effect = Exception("db down")
    topic_id = uuid.uuid4()

    with pytest.raises(Exception):
        repo.replace_all({(topic_id, "learning", "en"): {uuid.uuid4()}})

    session.rollback.assert_called_once()


def test_replace_all_writes_distinct_search_terms_per_topic_term_language_key(repo, session):
    topic_id = uuid.uuid4()

    repo.replace_all({
        (topic_id, "learning", "en"): {uuid.uuid4()},
        (topic_id, "學習", "zh-TW"): {uuid.uuid4()},
    })

    search_terms = session.add_all.call_args_list[0].args[0]
    assert len(search_terms) == 2
    langs = {t.language for t in search_terms}
    assert langs == {"en", "zh-TW"}
