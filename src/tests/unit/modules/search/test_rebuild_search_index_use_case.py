import uuid
from unittest.mock import MagicMock

from src.modules.search.application.use_cases.rebuild_search_index_use_case import RebuildSearchIndexUseCase


def _mock_session(rows):
    """`rows` are (topic_id, title, content) tuples — an article_id, no translation
    (t_language/t_title/t_content all None), are filled in automatically since most
    tests don't care about either."""
    session = MagicMock()
    full_rows = [
        (uuid.uuid4(), topic_id, title, content, None, None, None)
        for topic_id, title, content in rows
    ]
    session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.all.return_value = full_rows
    return session


def _mock_session_with_translations(rows):
    """`rows` are (article_id, topic_id, title, content, t_language, t_title, t_content)
    tuples, for tests that need to control the translation columns directly."""
    session = MagicMock()
    session.query.return_value.outerjoin.return_value.filter.return_value.filter.return_value.all.return_value = rows
    return session


def test_execute_writes_postgres_before_redis():
    topic_id = uuid.uuid4()
    session = _mock_session([(topic_id, "Machine Learning", "an article about machine learning and deep learning")])
    repo = MagicMock()
    gateway = MagicMock()
    call_order = []
    repo.replace_all.side_effect = lambda *a: call_order.append("postgres")
    gateway.rebuild.side_effect = lambda *a: call_order.append("redis")

    RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=1).execute()

    assert call_order == ["postgres", "redis"]


def test_execute_counts_document_frequency_not_raw_occurrence():
    topic_id = uuid.uuid4()
    # "learning" appears 3x within ONE article — must count once (document frequency).
    session = _mock_session([(topic_id, "learning learning learning", "")])
    repo = MagicMock()
    gateway = MagicMock()

    RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=1).execute()

    written = repo.replace_all.call_args.args[0]
    assert len(written[(topic_id, "learning", "en")]) == 1


def test_execute_redis_input_filters_terms_below_min_doc_freq():
    """min_doc_freq gates the Redis autocomplete trie's input (suggestion quality) —
    see the next test for confirmation it does NOT also gate the Postgres inverted
    index (that would break exact-match completeness for low-frequency terms)."""
    topic_a = uuid.uuid4()
    session = _mock_session([
        (topic_a, "rare term appears once", ""),
        (topic_a, "common term appears twice", ""),
        (topic_a, "another common mention", ""),
    ])
    repo = MagicMock()
    gateway = MagicMock()

    RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=2).execute()

    redis_written = gateway.rebuild.call_args.args[0]
    assert "common" in redis_written[topic_a]
    assert "rare" not in redis_written[topic_a]


def test_execute_postgres_input_is_not_filtered_by_min_doc_freq():
    """023-article-search follow-up: intelligence.search_terms/search_term_articles back
    exact-match retrieval's completeness guarantee, not just autocomplete suggestion
    quality — a term used in only one article must still be written there even though
    min_doc_freq=2 would exclude it from the Redis trie."""
    topic_a = uuid.uuid4()
    session = _mock_session([(topic_a, "rare term appears once", "")])
    repo = MagicMock()
    gateway = MagicMock()

    RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=2).execute()

    postgres_written = repo.replace_all.call_args.args[0]
    assert (topic_a, "rare", "en") in postgres_written

    redis_written = gateway.rebuild.call_args.args[0]
    assert "rare" not in redis_written.get(topic_a, {})


def test_execute_returns_summary_stats():
    topic_id = uuid.uuid4()
    session = _mock_session([(topic_id, "machine learning", "")])
    repo = MagicMock()
    gateway = MagicMock()

    stats = RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=1).execute()

    assert stats["article_count"] == 1
    assert stats["topic_count"] == 1
    assert stats["term_count"] == 2  # "machine", "learning"


def test_execute_indexes_translated_title_and_content():
    """Root-cause regression test: a zh-TW ArticleTranslation row must feed the same
    term extraction as the original title/content, or autocomplete/search never surfaces
    any Traditional Chinese terms regardless of the tokenizer's jieba support."""
    topic_id = uuid.uuid4()
    article_id = uuid.uuid4()
    session = _mock_session_with_translations([
        (article_id, topic_id, "Machine Learning", "", "zh-TW", "機器學習", "深度學習技術"),
    ])
    repo = MagicMock()
    gateway = MagicMock()

    RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=1).execute()

    redis_written = gateway.rebuild.call_args.args[0]
    assert "機器學習" in redis_written[topic_id] or "學習" in redis_written[topic_id]


def test_execute_tags_translated_terms_with_their_own_language_not_en():
    """023-article-search follow-up: intelligence.search_terms splits terms by language
    (unlike the Redis trie) — a translated term must be written under its own
    ArticleTranslation.language, not lumped in with the original's "en"."""
    topic_id = uuid.uuid4()
    article_id = uuid.uuid4()
    session = _mock_session_with_translations([
        (article_id, topic_id, "Machine Learning", "", "zh-TW", "機器學習", "深度學習技術"),
    ])
    repo = MagicMock()
    gateway = MagicMock()

    RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=1).execute()

    postgres_written = repo.replace_all.call_args.args[0]
    zh_keys = [key for key in postgres_written if key[0] == topic_id and key[2] == "zh-TW"]
    en_keys = [key for key in postgres_written if key[0] == topic_id and key[2] == "en"]
    assert any(key[1] in ("機器學習", "機器", "學習") for key in zh_keys)
    assert any(key[1] in ("machine", "learning") for key in en_keys)
    # No cross-contamination: the English terms must not also appear tagged zh-TW.
    assert not any(key[1] in ("machine", "learning") for key in zh_keys)


def test_execute_does_not_double_count_article_with_translation():
    """An article joined with exactly one translation row must still count as one
    article for document frequency — not two."""
    topic_id = uuid.uuid4()
    article_id = uuid.uuid4()
    session = _mock_session_with_translations([
        (article_id, topic_id, "machine learning", "", "zh-TW", "translated title", None),
    ])
    repo = MagicMock()
    gateway = MagicMock()

    stats = RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=1).execute()

    assert stats["article_count"] == 1
    postgres_written = repo.replace_all.call_args.args[0]
    assert len(postgres_written[(topic_id, "machine", "en")]) == 1


def test_execute_postgres_input_maps_term_to_the_set_of_article_ids():
    """repo.replace_all's contract: value is the *set of distinct article_ids* a term
    occurs in (not a count) — occurrence_count is derived from len() by the repository."""
    topic_id = uuid.uuid4()
    article_a = uuid.uuid4()
    article_b = uuid.uuid4()
    session = _mock_session_with_translations([
        (article_a, topic_id, "machine learning", "", None, None, None),
        (article_b, topic_id, "machine learning basics", "", None, None, None),
    ])
    repo = MagicMock()
    gateway = MagicMock()

    RebuildSearchIndexUseCase(session, repo, gateway, min_doc_freq=1).execute()

    postgres_written = repo.replace_all.call_args.args[0]
    assert postgres_written[(topic_id, "machine", "en")] == {article_a, article_b}
