import pytest
from unittest.mock import AsyncMock, MagicMock

from src.modules.intelligence.application.event_handlers.tag_counts_refresh_handler import (
    TagCountsRefreshHandler,
)


@pytest.mark.asyncio
async def test_handle_invokes_the_use_case():
    # RefreshTagArticleCountsUseCase.execute() stays a plain sync statement
    # (see handler docstring) — plain MagicMock, not AsyncMock.
    use_case = MagicMock()
    handler = TagCountsRefreshHandler(use_case)

    await handler.handle(event=AsyncMock())

    use_case.execute.assert_called_once()


@pytest.mark.asyncio
async def test_handle_never_raises_when_use_case_fails():
    use_case = MagicMock()
    use_case.execute.side_effect = RuntimeError("materialized view refresh failed")
    handler = TagCountsRefreshHandler(use_case)

    await handler.handle(event=AsyncMock())  # must not raise
