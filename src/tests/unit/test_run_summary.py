from src.infrastructure.shared.observability.run_summary import RunSummary, SourceResult


def test_record_new_increments_count():
    s = RunSummary()
    s.record_new("techcrunch")
    s.record_new("techcrunch")
    results = {r.source: r for r in s.get_results()}
    assert results["techcrunch"].new == 2


def test_record_duplicate_and_failed():
    s = RunSummary()
    s.record_duplicate("rss")
    s.record_failed("arxiv")
    results = {r.source: r for r in s.get_results()}
    assert results["rss"].duplicate == 1
    assert results["arxiv"].failed == 1