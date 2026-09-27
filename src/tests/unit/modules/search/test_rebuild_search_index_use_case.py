import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.modules.search.application.use_cases.rebuild_search_index_use_case import RebuildSearchIndexUseCase
from src.modules.search.domain.repositories.article_search_token_repository import TokenSource


def _source(title, content="", language="en", topic_id=None, updated_at=None):
    return TokenSource(
        article_id=uuid.uuid4(), language=language, topic_id=topic_id or uuid.uuid4(),
        title=title, content=content, source_updated_at=updated_at,
    )


def _repo(sources, deleted=0, term_counts=None):
    """Repository mock whose stale keys are exactly `sources`, served by load_sources()
    for whichever slice of keys is asked for."""
    repo = MagicMock()
    by_key = {(s.article_id, s.language): s for s in sources}
    repo.delete_ineligible.return_value = deleted
    repo.find_stale_keys.return_value = list(by_key)
    repo.load_sources.side_effect = lambda keys: [by_key[k] for k in keys]
    repo.term_counts_by_topic.return_value = term_counts or {}
    return repo


def _upserted(repo):
    return [row for call in repo.upsert.call_args_list for row in call.args[0]]


def test_execute_only_tokenizes_stale_sources():
    source = _source("Machine Learning", "an article about deep learning")
    repo = _repo([source])

    RebuildSearchIndexUseCase(repo, MagicMock()).execute()

    repo.find_stale_keys.assert_called_once_with(include_fresh=False)
    [row] = _upserted(repo)
    assert (row.article_id, row.language, row.topic_id) == (source.article_id, "en", source.topic_id)
    assert {"machine", "learning"} <= set(row.tokens)
    assert "an" not in row.tokens  # stopword
    assert row.tokens == sorted(set(row.tokens))  # deduped, deterministic order


def test_execute_full_asks_for_every_eligible_source():
    repo = _repo([])

    RebuildSearchIndexUseCase(repo, MagicMock()).execute(full=True)

    repo.find_stale_keys.assert_called_once_with(include_fresh=True)


def test_execute_deletes_ineligible_rows_before_indexing():
    repo = _repo([_source("Quantum")])
    call_order = []
    repo.delete_ineligible.side_effect = lambda: call_order.append("delete") or 0
    repo.upsert.side_effect = lambda rows: call_order.append("upsert")

    RebuildSearchIndexUseCase(repo, MagicMock()).execute()

    assert call_order == ["delete", "upsert"]


def test_execute_carries_translation_language_and_updated_at():
    updated_at = datetime(2026, 9, 1, tzinfo=timezone.utc)
    repo = _repo([_source("準晶體", "準晶體 晶格", language="zh-TW", updated_at=updated_at)])

    RebuildSearchIndexUseCase(repo, MagicMock()).execute()

    [row] = _upserted(repo)
    assert row.language == "zh-TW"
    assert row.source_updated_at == updated_at
    assert "準晶體" in row.tokens


def test_execute_upserts_sources_in_batches():
    repo = _repo([_source(f"term{i}") for i in range(5)])

    RebuildSearchIndexUseCase(repo, MagicMock(), batch_size=2).execute()

    assert [len(call.args[0]) for call in repo.upsert.call_args_list] == [2, 2, 1]
    assert len(_upserted(repo)) == 5


def test_execute_stores_an_empty_token_list_rather_than_skipping():
    """A source whose text is all stopwords still gets a row — otherwise it would be
    'missing' and re-tokenized on every run forever."""
    repo = _repo([_source("the a an", "of")])

    RebuildSearchIndexUseCase(repo, MagicMock()).execute()

    [row] = _upserted(repo)
    assert row.tokens == []


def test_execute_writes_postgres_before_redis():
    repo = _repo([_source("Quantum")])
    gateway = MagicMock()
    call_order = []
    repo.upsert.side_effect = lambda rows: call_order.append("upsert")
    repo.refresh_term_counts.side_effect = lambda: call_order.append("refresh")
    gateway.rebuild.side_effect = lambda *a: call_order.append("redis")

    RebuildSearchIndexUseCase(repo, gateway).execute()

    assert call_order == ["upsert", "refresh", "redis"]


def test_execute_rebuilds_redis_from_repo_term_counts_with_min_doc_freq():
    topic_id = uuid.uuid4()
    term_counts = {topic_id: {"quantum": 3}}
    repo = _repo([], term_counts=term_counts)
    gateway = MagicMock()

    RebuildSearchIndexUseCase(repo, gateway, min_doc_freq=3).execute()

    repo.term_counts_by_topic.assert_called_once_with(3)
    gateway.rebuild.assert_called_once_with(term_counts)


def test_execute_returns_summary_stats():
    topic_id = uuid.uuid4()
    repo = _repo(
        [_source("Quantum"), _source("Lattice")], deleted=4,
        term_counts={topic_id: {"quantum": 2, "lattice": 2}},
    )

    stats = RebuildSearchIndexUseCase(repo, MagicMock()).execute()

    assert stats == {"indexed_count": 2, "deleted_count": 4, "topic_count": 1, "term_count": 2}


def test_execute_with_nothing_stale_still_refreshes_read_models():
    repo = _repo([])
    gateway = MagicMock()

    RebuildSearchIndexUseCase(repo, gateway).execute()

    repo.load_sources.assert_not_called()
    repo.upsert.assert_not_called()
    repo.refresh_term_counts.assert_called_once()
    gateway.rebuild.assert_called_once()
