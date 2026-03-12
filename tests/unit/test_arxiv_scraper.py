import responses
from datetime import datetime, timedelta, timezone

RECENT = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atom(entries_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        + entries_xml
        + "</feed>"
    )


def _entry(paper_id="2401.00001", version="v1", title="Digital Twins Research",
           summary="Abstract text.", published=None, authors=None):
    published = published or RECENT
    author_xml = "".join(
        f"<author><name>{a}</name></author>" for a in (authors or ["John Doe"])
    )
    return (
        f"<entry>"
        f"<id>http://arxiv.org/abs/{paper_id}{version}</id>"
        f"<title>{title}</title>"
        f"<summary>{summary}</summary>"
        f"<published>{published}</published>"
        f"{author_xml}"
        f'<link href="http://arxiv.org/abs/{paper_id}{version}" rel="alternate" type="text/html"/>'
        f"</entry>"
    )


# ── constructor ────────────────────────────────────────────────────────────

def test_fetch_pdf_is_true_by_default():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    assert ArxivScraper().fetch_pdf is True


def test_respects_max_results():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    assert ArxivScraper(max_results=50).max_results == 50


def test_builds_query_contains_digital_twin_terms():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    q = ArxivScraper()._build_query()
    assert "digital" in q.lower() or "twin" in q.lower()


# ── discover() ────────────────────────────────────────────────────────────

@responses.activate
def test_discover_returns_one_task_per_entry():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry()), status=200)
    tasks = ArxivScraper(fetch_pdf=False).discover()
    assert len(tasks) == 1
    assert tasks[0].url == "http://arxiv.org/abs/2401.00001v1"
    assert tasks[0].source == "arxiv"


@responses.activate
def test_discover_returns_empty_on_api_error():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query", status=500)
    assert ArxivScraper().discover() == []


@responses.activate
def test_discover_filters_old_papers():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(published=old)), status=200)
    assert ArxivScraper(days_back=7).discover() == []


# ── task.execute() ────────────────────────────────────────────────────────

@responses.activate
def test_execute_returns_article_with_abstract_when_fetch_pdf_false():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(summary="Short abstract.")), status=200)
    article = ArxivScraper(fetch_pdf=False).discover()[0].execute()
    assert article is not None
    assert article.content == "Short abstract."
    assert article.source == "arxiv"
    assert article.metadata["pdf_available"] is False


@responses.activate
def test_execute_extracts_authors():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(authors=["Alice", "Bob"])), status=200)
    article = ArxivScraper(fetch_pdf=False).discover()[0].execute()
    assert article.metadata["authors"] == ["Alice", "Bob"]


@responses.activate
def test_execute_falls_back_to_abstract_when_pdf_fails():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00002", summary="Fallback.")), status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00002v1", status=404)
    article = ArxivScraper(fetch_pdf=True).discover()[0].execute()
    assert article.content == "Fallback."
    assert article.metadata["pdf_available"] is False


@responses.activate
def test_execute_uses_pdf_text_and_sets_pdf_available_true():
    from unittest.mock import patch
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00003", summary="Short abstract.")),
                  status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00003v1",
                  body=b"%PDF-1.4 fake", status=200)
    with patch(
        "src.scrapers.content_parsers.pdf_parser.PdfParser.parse",
        return_value="Full PDF text."
    ):
        article = ArxivScraper(fetch_pdf=True).discover()[0].execute()
    assert article.metadata["pdf_available"] is True
    assert article.content == "Full PDF text."
    assert article.metadata["abstract"] == "Short abstract."


@responses.activate
def test_discover_handles_entry_with_missing_summary():
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    entry_xml = (
        f"<entry>"
        f"<id>http://arxiv.org/abs/2401.00004v1</id>"
        f"<title>Minimal Entry</title>"
        f"<summary></summary>"
        f"<published>{RECENT}</published>"
        f"</entry>"
    )
    responses.add(responses.GET, "http://export.arxiv.org/api/query",
                  body=_atom(entry_xml), status=200)
    tasks = ArxivScraper(fetch_pdf=False).discover()
    assert len(tasks) == 1
    article = tasks[0].execute()
    assert article.title == "Minimal Entry"
    assert article.content == ""