from src.observability.run_summary import RunSummary, SourceResult


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


def test_totals():
    s = RunSummary()
    s.record_new("a")
    s.record_new("a")
    s.record_duplicate("b")
    s.record_failed("c")
    assert s.total_new() == 2
    assert s.total_duplicate() == 1
    assert s.total_failed() == 1


def test_multiple_sources_are_independent():
    s = RunSummary()
    s.record_new("src1")
    s.record_failed("src2")
    results = {r.source: r for r in s.get_results()}
    assert results["src1"].failed == 0
    assert results["src2"].new == 0
