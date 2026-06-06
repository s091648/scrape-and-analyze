"""Shared test fixtures for intelligence application use case tests."""
import uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from src.modules.intelligence.domain.value_objects import AnalysisTagGroup


# ── Value objects for normalization tests ────────────────────────────────────


@dataclass
class TagData:
    """Lightweight tag data for test assertions."""
    name: str
    tag_group_name: str
    embedding: list | None = None


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_embedding_vector():
    """Return a 768-dim unit vector for embedding tests."""
    vec = [0.0] * 768
    vec[0] = 1.0
    return vec


@pytest.fixture
def sample_tag_groups():
    """Return sample AnalysisTagGroup list for normalization tests."""
    return [
        AnalysisTagGroup(group_name="research_methods", tags=["transformer", "attention"]),
        AnalysisTagGroup(group_name="applications", tags=["object detection"]),
    ]


@pytest.fixture
def tag_data_factory():
    """Factory for creating TagData instances."""
    def _factory(name="TestTag", group="test_group", embedding=None):
        return TagData(name=name, tag_group_name=group, embedding=embedding)
    return _factory


@pytest.fixture
def mock_tag_repo():
    """Pre-configured mock TagRepository for normalization tests."""
    repo = MagicMock()
    repo.find_by_group.return_value = []
    repo.save.return_value = MagicMock(name="saved_tag")
    repo.commit = MagicMock()
    return repo


@pytest.fixture
def mock_embedding_service():
    """Pre-configured mock EmbeddingService."""
    svc = MagicMock()
    svc.embed_batch.return_value = [[0.0] * 768]
    return svc


@pytest.fixture
def mock_event_bus():
    """Pre-configured mock EventBus."""
    bus = MagicMock()
    return bus
