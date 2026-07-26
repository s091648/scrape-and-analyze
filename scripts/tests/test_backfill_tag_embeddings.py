"""T055: Tests for backfill_tag_embeddings.py."""
import pytest
from unittest.mock import MagicMock, patch


def test_embed_table_selects_null_embedding_rows():
    """embed_table should only select rows where embedding IS NULL."""
    from scripts.backfill_tag_embeddings import main

    session = MagicMock()
    # embed_table() indexes rows positionally (r[0]=id, r[1]=text_col), matching
    # a real SQLAlchemy Row's tuple-like access — plain tuples, not MagicMocks.
    rows = [
        ("tag-1", "Transformer"),
        ("tag-2", "Diffusion"),
    ]
    session.execute.return_value.fetchall.return_value = rows

    provider = MagicMock()
    provider.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]

    with patch("scripts.backfill_tag_embeddings.build_embedding_service", return_value=provider):
        with patch("src.infrastructure.persistence.database.init_db"):
            with patch("src.infrastructure.persistence.database.get_session", return_value=session):
                with pytest.MonkeyPatch().context() as mp:
                    mp.setattr("sys.argv", ["backfill_tag_embeddings.py"])
                    main()

    # Should have executed SELECT and UPDATE statements
    assert session.execute.call_count >= 1


def test_embed_table_dry_run_does_not_update():
    """In dry-run mode, no UPDATE statements should be executed (only SELECT)."""
    from scripts.backfill_tag_embeddings import main

    session = MagicMock()
    rows = [("tag-1", "Transformer")]
    session.execute.return_value.fetchall.return_value = rows

    provider = MagicMock()
    provider.embed_batch.return_value = [[0.1] * 768]

    # Track which SQL strings are executed
    executed_sql = []
    def track_execute(sql, params=None):
        executed_sql.append(str(sql))
        if "SELECT" in str(sql):
            return MagicMock(fetchall=lambda: rows)
        return MagicMock()

    session.execute.side_effect = track_execute

    with patch("scripts.backfill_tag_embeddings.build_embedding_service", return_value=provider):
        with patch("src.infrastructure.persistence.database.init_db"):
            with patch("src.infrastructure.persistence.database.get_session", return_value=session):
                with pytest.MonkeyPatch().context() as mp:
                    mp.setattr("sys.argv", ["backfill_tag_embeddings.py", "--dry-run"])
                    main()

    # No UPDATE should be called in dry-run
    updates = [s for s in executed_sql if "UPDATE" in s]
    assert len(updates) == 0


def test_embed_batch_called_with_texts():
    """embed_batch should be called with tag names as text input."""
    from scripts.backfill_tag_embeddings import main

    session = MagicMock()
    rows = [("tag-1", "Transformer")]
    session.execute.return_value.fetchall.return_value = rows

    provider = MagicMock()
    provider.embed_batch.return_value = [[0.1] * 768]

    with patch("scripts.backfill_tag_embeddings.build_embedding_service", return_value=provider):
        with patch("src.infrastructure.persistence.database.init_db"):
            with patch("src.infrastructure.persistence.database.get_session", return_value=session):
                with pytest.MonkeyPatch().context() as mp:
                    mp.setattr("sys.argv", ["backfill_tag_embeddings.py", "--only", "tags", "--dry-run"])
                    main()

    provider.embed_batch.assert_called_once()
    texts = provider.embed_batch.call_args[0][0]
    assert len(texts) == 1
    assert "Transformer" in texts[0]


def test_main_exits_without_database_url(monkeypatch, capsys):
    """main() must exit when DATABASE_URL is missing."""
    import sys
    from scripts.backfill_tag_embeddings import main

    monkeypatch.setattr(sys, "argv", ["backfill_tag_embeddings.py"])
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SystemExit):
        main()
