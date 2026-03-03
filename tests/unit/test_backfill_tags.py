import pytest
from unittest.mock import MagicMock


def test_find_articles_returns_rows():
    """find_articles_needing_backfill returns all rows from session"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = [
        MagicMock(id="art-1", title="T1", content="C1", analysis_id="an-1"),
    ]

    rows = find_articles_needing_backfill(session)

    assert len(rows) == 1
    session.execute.assert_called_once()


def test_find_articles_passes_limit():
    """find_articles_needing_backfill passes limit to query when given"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    find_articles_needing_backfill(session, limit=5)

    call_args = session.execute.call_args
    # limit value must appear in the params dict
    assert call_args[0][1] == {"limit": 5}


def test_find_articles_no_limit_omits_param():
    """find_articles_needing_backfill omits params when no limit"""
    from scripts.backfill_tags import find_articles_needing_backfill

    session = MagicMock()
    session.execute.return_value.fetchall.return_value = []

    find_articles_needing_backfill(session, limit=None)

    call_args = session.execute.call_args
    # called with just the text object, no params dict
    assert len(call_args[0]) == 1


def test_upsert_tags_dry_run_does_not_call_session(capsys):
    """dry_run=True must not execute any DB statements"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    tag_groups = [{"group": "digital_twin", "tags": ["virtual replica", "real-time sync"]}]

    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=True)

    session.execute.assert_not_called()
    out = capsys.readouterr().out
    assert "virtual replica" in out
    assert "real-time sync" in out


def test_upsert_tags_executes_three_statements_per_tag():
    """Each tag triggers INSERT tag, SELECT tag id, INSERT article_tag"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    # SELECT returns a row with an id
    session.execute.return_value.first.return_value = ("tag-id-123",)

    tag_groups = [{"group": "digital_twin", "tags": ["virtual replica"]}]
    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=False)

    assert session.execute.call_count == 3  # INSERT tag, SELECT id, INSERT article_tag


def test_upsert_tags_skips_empty_tag_names():
    """Tags with empty/None name must be silently skipped"""
    from scripts.backfill_tags import upsert_tags_for_article

    session = MagicMock()
    session.execute.return_value.first.return_value = ("tag-id",)

    tag_groups = [{"group": "digital_twin", "tags": ["", None, "valid-tag"]}]
    upsert_tags_for_article(session, "art-uuid", tag_groups, dry_run=False)

    # Only 1 valid tag → 3 execute calls
    assert session.execute.call_count == 3


def _make_result():
    from src.analyzers.llm_provider import AnalysisResult
    return AnalysisResult(
        tag_groups=[],
        pain_points="pain",
        insights="insight",
        innovations="innovation",
        input_tokens=10,
        output_tokens=5,
    )


def test_update_analysis_dry_run_skips_db(capsys):
    """dry_run=True must not call session.execute"""
    from scripts.backfill_tags import update_analysis

    session = MagicMock()
    update_analysis(session, "an-id", _make_result(), model_used="gemini-2.0-flash", dry_run=True)

    session.execute.assert_not_called()
    out = capsys.readouterr().out
    assert "an-id" in out


def test_update_analysis_executes_update():
    """update_analysis should call session.execute exactly once"""
    from scripts.backfill_tags import update_analysis

    session = MagicMock()
    update_analysis(session, "an-id", _make_result(), model_used="gemini-2.0-flash", dry_run=False)

    session.execute.assert_called_once()
    # Verify the params dict includes expected keys
    params = session.execute.call_args[0][1]
    assert params["pain_points"] == "pain"
    assert params["insights"] == "insight"
    assert params["innovations"] == "innovation"
    assert params["model_used"] == "gemini-2.0-flash"
    assert params["input_tokens"] == 10
    assert params["output_tokens"] == 5


def _make_provider(result):
    """Return a mock GeminiProvider that returns `result` from analyze()."""
    provider = MagicMock()
    provider.model_name = "gemini-2.0-flash"
    provider.analyze.return_value = result
    return provider


def test_run_backfill_processes_successful_articles():
    """Processed count increments when LLM succeeds"""
    from scripts.backfill_tags import run_backfill

    session = MagicMock()
    rows = [MagicMock(id="art-1", title="T", content="C", analysis_id="an-1")]

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "scripts.backfill_tags.find_articles_needing_backfill",
            lambda s, limit=None: rows,
        )
        stats = run_backfill(session, _make_provider(_make_result()), "prompt", dry_run=True)

    assert stats["processed"] == 1
    assert stats["skipped"] == 0


def test_run_backfill_skips_on_llm_failure():
    """Skipped count increments when LLM returns None"""
    from scripts.backfill_tags import run_backfill

    session = MagicMock()
    rows = [MagicMock(id="art-1", title="T", content="C", analysis_id="an-1")]

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "scripts.backfill_tags.find_articles_needing_backfill",
            lambda s, limit=None: rows,
        )
        stats = run_backfill(session, _make_provider(None), "prompt", dry_run=False)

    assert stats["processed"] == 0
    assert stats["skipped"] == 1


def test_run_backfill_commits_per_article_when_not_dry_run():
    """session.commit() is called once per successfully processed article"""
    from scripts.backfill_tags import run_backfill

    session = MagicMock()
    rows = [
        MagicMock(id="art-1", title="T1", content="C1", analysis_id="an-1"),
        MagicMock(id="art-2", title="T2", content="C2", analysis_id="an-2"),
    ]

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "scripts.backfill_tags.find_articles_needing_backfill",
            lambda s, limit=None: rows,
        )
        run_backfill(session, _make_provider(_make_result()), "prompt", dry_run=False)

    assert session.commit.call_count == 2


def test_run_backfill_dry_run_does_not_commit():
    """session.commit() must not be called in dry_run mode"""
    from scripts.backfill_tags import run_backfill

    session = MagicMock()
    rows = [MagicMock(id="art-1", title="T", content="C", analysis_id="an-1")]

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "scripts.backfill_tags.find_articles_needing_backfill",
            lambda s, limit=None: rows,
        )
        run_backfill(session, _make_provider(_make_result()), "prompt", dry_run=True)

    session.commit.assert_not_called()


def test_main_exits_without_llm_api_key(monkeypatch, capsys):
    """main() must exit(1) when LLM_API_KEY is missing"""
    import sys
    from scripts.backfill_tags import main

    monkeypatch.setattr(sys, "argv", ["backfill_tags.py"])
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "LLM_API_KEY" in capsys.readouterr().err


def test_main_exits_without_database_url(monkeypatch, capsys):
    """main() must exit(1) when DATABASE_URL is missing"""
    import sys
    from scripts.backfill_tags import main

    monkeypatch.setattr(sys, "argv", ["backfill_tags.py"])
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "DATABASE_URL" in capsys.readouterr().err
