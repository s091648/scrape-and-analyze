"""US5 (024-async-pipeline-refactor) tests: every pipeline stage depends only
on the abstract EventBus Protocol (src/shared/application/ports/event_bus.py),
never a concrete implementation — a future Redis Streams-backed EventBus
would be a drop-in swap requiring no changes to any handler/use-case code.

T064: substituting StubEventBus for AsyncInMemoryEventBus in
      build_collection_pipeline()'s wiring still constructs successfully.
T065: static check — no module outside src/infrastructure/shared/events/ and
      src/bootstrap.py imports AsyncInMemoryEventBus directly.
"""
import ast
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tests.unit.fixtures.stub_event_bus import StubEventBus

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"

ALLOWED_PATHS = {
    SRC_ROOT / "bootstrap.py",
    SRC_ROOT / "infrastructure" / "shared" / "events" / "in_memory_event_bus.py",
}


def _imports_async_in_memory_event_bus(py_file: Path) -> bool:
    """True if py_file has a Python import statement naming
    AsyncInMemoryEventBus — comments/docstrings mentioning the name don't
    count, only real `import`/`from ... import ...` statements."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == "AsyncInMemoryEventBus" for alias in node.names):
                return True
        elif isinstance(node, ast.Import):
            if any(alias.name == "AsyncInMemoryEventBus" for alias in node.names):
                return True
    return False


# ---------------------------------------------------------------------------
# T065: static import-boundary check
# ---------------------------------------------------------------------------

def test_only_bootstrap_and_events_module_import_async_in_memory_event_bus():
    violations = []
    for py_file in SRC_ROOT.rglob("*.py"):
        if "tests" in py_file.relative_to(SRC_ROOT).parts:
            continue  # test fixtures/wiring are expected to construct concrete buses
        if py_file in ALLOWED_PATHS:
            continue
        if _imports_async_in_memory_event_bus(py_file):
            violations.append(str(py_file.relative_to(REPO_ROOT)))

    assert violations == [], (
        "These modules import AsyncInMemoryEventBus directly instead of "
        "depending only on the EventBus Protocol: " + ", ".join(violations)
    )


# ---------------------------------------------------------------------------
# T064: build_collection_pipeline() constructs with a stub EventBus swapped in
# ---------------------------------------------------------------------------

def _make_collection_pipeline_mocks():
    mock_session = MagicMock()
    mock_llm = MagicMock()
    mock_embedding = MagicMock()
    mock_init_db = MagicMock()
    mock_get_session = MagicMock(return_value=mock_session)
    mock_build_async_llm = MagicMock(return_value=(mock_llm, mock_embedding, ["gemini"]))
    mock_build_async_rag = MagicMock(return_value=(None, None))
    mock_get_async_sessionmaker = MagicMock(return_value=MagicMock())
    return (mock_init_db, mock_get_session, mock_build_async_llm,
            mock_build_async_rag, mock_get_async_sessionmaker)


def test_build_collection_pipeline_constructs_with_stub_event_bus_swapped_in():
    (mock_init_db, mock_get_session, mock_build_async_llm,
     mock_build_async_rag, mock_get_async_sessionmaker) = _make_collection_pipeline_mocks()

    with patch("src.bootstrap.init_db", mock_init_db), \
         patch("src.bootstrap.get_session", mock_get_session), \
         patch("src.bootstrap.build_async_llm_service", mock_build_async_llm), \
         patch("src.bootstrap.build_async_rag_ingestion_service", mock_build_async_rag), \
         patch("src.infrastructure.persistence.database.get_async_sessionmaker", mock_get_async_sessionmaker), \
         patch("src.infrastructure.shared.events.in_memory_event_bus.AsyncInMemoryEventBus", StubEventBus):
        from src.bootstrap import build_collection_pipeline
        pipeline, _ = asyncio.run(build_collection_pipeline())

    assert isinstance(pipeline._event_bus, StubEventBus)
    assert pipeline._event_bus_factory is StubEventBus
