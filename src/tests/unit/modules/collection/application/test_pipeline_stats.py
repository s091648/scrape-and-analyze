from src.modules.collection.application.use_cases import ArticleOutcome


def test_record_new_increments_new_count():
    from src.modules.collection.application.use_cases import PipelineStats
    stats = PipelineStats()
    stats.record("arxiv", ArticleOutcome.NEW)
    stats.record("arxiv", ArticleOutcome.NEW)
    results = stats.get_results()
    assert len(results) == 1
    assert results[0].source == "arxiv"
    assert results[0].new == 2
    assert results[0].duplicate == 0
    assert results[0].failed == 0


def test_record_duplicate_increments_duplicate_count():
    from src.modules.collection.application.use_cases import PipelineStats
    stats = PipelineStats()
    stats.record("rss", ArticleOutcome.DUPLICATE)
    results = stats.get_results()
    assert results[0].duplicate == 1
    assert results[0].new == 0


def test_record_failed_increments_failed_count():
    from src.modules.collection.application.use_cases import PipelineStats
    stats = PipelineStats()
    stats.record("blog", ArticleOutcome.FAILED)
    results = stats.get_results()
    assert results[0].failed == 1


def test_multiple_sources_tracked_separately():
    from src.modules.collection.application.use_cases import PipelineStats
    stats = PipelineStats()
    stats.record("arxiv", ArticleOutcome.NEW)
    stats.record("rss", ArticleOutcome.DUPLICATE)
    results = {r.source: r for r in stats.get_results()}
    assert results["arxiv"].new == 1
    assert results["rss"].duplicate == 1


def test_thread_safety_under_concurrent_writes():
    import threading
    from src.modules.collection.application.use_cases import PipelineStats
    stats = PipelineStats()
    threads = [
        threading.Thread(target=stats.record, args=("arxiv", ArticleOutcome.NEW))
        for _ in range(100)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    results = stats.get_results()
    assert results[0].new == 100


def test_empty_stats_returns_empty_list():
    from src.modules.collection.application.use_cases import PipelineStats
    stats = PipelineStats()
    assert stats.get_results() == []