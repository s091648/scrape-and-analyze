from unittest.mock import MagicMock


def _make_mock_embed_response(vectors):
    response = MagicMock()
    response.embeddings = [MagicMock(values=v) for v in vectors]
    return response


def test_embed_returns_768_dim_vector():
    from src.infrastructure.intelligence.embedding.gemini_embedding_provider import GeminiEmbeddingProvider
    provider = GeminiEmbeddingProvider(api_key="test-key")
    provider._client = MagicMock()
    provider._client.models.embed_content.return_value = _make_mock_embed_response([[0.1] * 768])

    result = provider.embed("hello world")

    assert len(result) == 768
    assert result[0] == 0.1
    provider._client.models.embed_content.assert_called_once_with(
        model="gemini-embedding-001",
        contents=["hello world"],
        config={"task_type": "CLASSIFICATION", "output_dimensionality": 768},
    )


def test_embed_batch_returns_one_vector_per_text():
    from src.infrastructure.intelligence.embedding.gemini_embedding_provider import GeminiEmbeddingProvider
    provider = GeminiEmbeddingProvider(api_key="test-key")
    provider._client = MagicMock()
    provider._client.models.embed_content.return_value = _make_mock_embed_response(
        [[0.1] * 768, [0.2] * 768]
    )

    results = provider.embed_batch(["text one", "text two"])

    assert len(results) == 2
    assert len(results[0]) == 768
    assert len(results[1]) == 768


def test_embed_batch_splits_at_100():
    from src.infrastructure.intelligence.embedding.gemini_embedding_provider import GeminiEmbeddingProvider
    provider = GeminiEmbeddingProvider(api_key="test-key")
    provider._client = MagicMock()
    provider._client.models.embed_content.return_value = _make_mock_embed_response(
        [[0.1] * 768] * 100
    )

    texts = [f"text {i}" for i in range(150)]
    provider.embed_batch(texts)

    assert provider._client.models.embed_content.call_count == 2
