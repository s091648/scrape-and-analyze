from unittest.mock import MagicMock

from src.modules.intelligence.application.use_cases.refresh_tag_article_counts_use_case import (
    RefreshTagArticleCountsUseCase,
)


def _make_session_with_connection():
    """Mimics session.get_bind().connect().execution_options(...) as a context
    manager, mirroring how RefreshTagArticleCountsUseCase.execute() uses it."""
    session = MagicMock()
    conn_cm = MagicMock()
    conn = MagicMock()
    conn_cm.__enter__ = MagicMock(return_value=conn)
    conn_cm.__exit__ = MagicMock(return_value=False)
    session.get_bind.return_value.connect.return_value.execution_options.return_value = conn_cm
    return session, conn


def test_execute_refreshes_materialized_view_concurrently():
    session, conn = _make_session_with_connection()
    use_case = RefreshTagArticleCountsUseCase(session=session)

    use_case.execute()

    conn.execute.assert_called_once()
    executed_sql = str(conn.execute.call_args[0][0])
    assert "REFRESH MATERIALIZED VIEW CONCURRENTLY" in executed_sql
    assert "intelligence.tag_article_counts" in executed_sql


def test_execute_opens_connection_in_autocommit_mode():
    """REFRESH MATERIALIZED VIEW CONCURRENTLY cannot run inside a transaction
    block, so execute() must open its own AUTOCOMMIT connection off the
    session's engine rather than reusing the session's ambient transaction."""
    session, _conn = _make_session_with_connection()
    use_case = RefreshTagArticleCountsUseCase(session=session)

    use_case.execute()

    session.get_bind.return_value.connect.return_value.execution_options.assert_called_once_with(
        isolation_level="AUTOCOMMIT"
    )


def test_execute_propagates_exceptions_from_the_connection():
    session, conn = _make_session_with_connection()
    conn.execute.side_effect = RuntimeError("db down")
    use_case = RefreshTagArticleCountsUseCase(session=session)

    try:
        use_case.execute()
        assert False, "expected RuntimeError to propagate"
    except RuntimeError:
        pass
