from unittest.mock import MagicMock, patch

from src.modules.collection.application.events import PipelineCompletedEvent
from src.modules.collection.application.event_handlers.cache_warmup_handler import CacheWarmupHandler
from src.modules.collection.application.use_cases import SourceStats

_MODULE = "src.modules.collection.application.event_handlers.cache_warmup_handler"


def _make_event():
    return PipelineCompletedEvent(
        stats=[SourceStats(source="arxiv", new=3, duplicate=1, failed=0)],
        duration_seconds=8.0,
    )


def _ok_response(json_body):
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status.return_value = None
    return resp


def test_warms_topic_less_and_per_topic_default_reads():
    with patch(f"{_MODULE}.requests.post") as mock_post, patch(f"{_MODULE}.requests.get") as mock_get:
        mock_post.return_value = _ok_response({"access_token": "guest-tok"})
        mock_get.side_effect = lambda url, **kwargs: (
            _ok_response([{"id": "topic-1"}, {"id": "topic-2"}]) if url.endswith("/topics") else _ok_response({})
        )

        CacheWarmupHandler(backend_url="http://backend:8000").handle(_make_event())

    mock_post.assert_called_once_with("http://backend:8000/auth/guest", timeout=15)

    called_paths = [
        (c.args[0].removeprefix("http://backend:8000"), c.kwargs.get("params"))
        for c in mock_get.call_args_list
    ]
    # topic-less defaults (no /weekly-reports/latest — it requires topic_id)
    assert ("/articles", None) in called_paths
    assert ("/analyses/graph", None) in called_paths
    assert ("/tag-groups", None) in called_paths
    assert not any(p == "/weekly-reports/latest" and params is None for p, params in called_paths)
    # per-topic defaults, once per active topic
    for topic_id in ("topic-1", "topic-2"):
        params = {"topic_id": topic_id}
        assert ("/articles", params) in called_paths
        assert ("/analyses/graph", params) in called_paths
        assert ("/tag-groups", params) in called_paths
        assert ("/weekly-reports/latest", params) in called_paths


def test_guest_token_failure_does_not_raise_and_skips_warming():
    with patch(f"{_MODULE}.requests.post", side_effect=Exception("backend unreachable")) as mock_post, \
         patch(f"{_MODULE}.requests.get") as mock_get:
        CacheWarmupHandler(backend_url="http://backend:8000").handle(_make_event())

    mock_post.assert_called_once()
    mock_get.assert_not_called()


def test_single_warm_request_failure_does_not_abort_the_rest():
    with patch(f"{_MODULE}.requests.post") as mock_post, patch(f"{_MODULE}.requests.get") as mock_get:
        mock_post.return_value = _ok_response({"access_token": "guest-tok"})

        def _get(url, **kwargs):
            if url.endswith("/topics"):
                return _ok_response([])
            if url.endswith("/articles"):
                raise Exception("transient failure")
            return _ok_response({})

        mock_get.side_effect = _get

        # Must not raise despite /articles failing.
        CacheWarmupHandler(backend_url="http://backend:8000").handle(_make_event())

    called_paths = [c.args[0] for c in mock_get.call_args_list]
    assert any(p.endswith("/analyses/graph") for p in called_paths)
    assert any(p.endswith("/tag-groups") for p in called_paths)
