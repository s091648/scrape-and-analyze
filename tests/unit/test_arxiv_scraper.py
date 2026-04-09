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
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    assert ArxivScraper().fetch_pdf is True


def test_respects_max_results():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    assert ArxivScraper(max_results=50).max_results == 50


def test_builds_query_contains_digital_twin_terms():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    q = ArxivScraper()._build_query()
    assert "digital" in q.lower() or "twin" in q.lower()


# ── discover() ────────────────────────────────────────────────────────────

@responses.activate
def test_discover_returns_one_task_per_entry():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry()), status=200)
    tasks = ArxivScraper(fetch_pdf=False).discover()
    assert len(tasks) == 1
    assert tasks[0].url == "http://arxiv.org/abs/2401.00001v1"
    assert tasks[0].source == "arxiv"


@responses.activate
def test_discover_returns_empty_on_api_error():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query", status=500)
    assert ArxivScraper().discover() == []


@responses.activate
def test_discover_filters_old_papers():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(published=old)), status=200)
    assert ArxivScraper(days_back=7).discover() == []


# ── task.execute() ────────────────────────────────────────────────────────

@responses.activate
def test_execute_returns_article_with_abstract_when_fetch_pdf_false():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(summary="Short abstract.")), status=200)
    article = ArxivScraper(fetch_pdf=False).discover()[0].execute()
    assert article is not None
    assert article.content == "Short abstract."
    assert article.source == "arxiv"
    assert article.metadata["pdf_available"] is False


@responses.activate
def test_execute_extracts_authors():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(authors=["Alice", "Bob"])), status=200)
    article = ArxivScraper(fetch_pdf=False).discover()[0].execute()
    assert article.metadata["authors"] == ["Alice", "Bob"]


@responses.activate
def test_execute_falls_back_to_abstract_when_pdf_fails():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00002", summary="Fallback.")), status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00002v1", status=404)
    article = ArxivScraper(fetch_pdf=True).discover()[0].execute()
    assert article.content == "Fallback."
    assert article.metadata["pdf_available"] is False


@responses.activate
def test_execute_uses_sections_and_sets_pdf_available_true():
    from unittest.mock import patch
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00003", summary="Short abstract.")),
                  status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00003v1",
                  body=b"%PDF-1.4 fake", status=200)
    with patch("src.ingestion.parsers.pdf_parser.PdfParser.parse",
               return_value="Full PDF text."), \
         patch("src.ingestion.parsers.pdf_parser.PdfParser.extract_sections",
               return_value={"introduction": "Intro text.", "conclusion": "Conclusion."}):
        article = ArxivScraper(fetch_pdf=True).discover()[0].execute()
    assert article.metadata["pdf_available"] is True
    assert article.content == "Short abstract."
    assert "pdf_text" not in article.metadata
    assert article.metadata["sections"] == {"introduction": "Intro text.", "conclusion": "Conclusion."}


@responses.activate
def test_execute_strips_null_bytes_from_sections():
    from unittest.mock import patch
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00009", summary="Abstract.")),
                  status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00009v1",
                  body=b"%PDF-1.4 fake", status=200)
    with patch("src.ingestion.parsers.pdf_parser.PdfParser.parse",
               return_value="text with \x00 null"), \
         patch("src.ingestion.parsers.pdf_parser.PdfParser.extract_sections",
               return_value={"introduction": "Hello \x00 world."}):
        article = ArxivScraper(fetch_pdf=True).discover()[0].execute()
    assert "\x00" not in article.metadata["sections"].get("introduction", "")


def test_arxiv_scraper_uses_selector_config_keywords():
    from unittest.mock import MagicMock, patch
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    client = MagicMock()
    client.fetch_entries.return_value = []
    scraper = ArxivScraper(
        keywords=["ti:\"3d ai\"", "ti:\"neural rendering\""],
        client=client,
    )
    scraper.discover()
    call_kwargs = client.fetch_entries.call_args[1]
    assert "3d ai" in call_kwargs["query"]
    assert "neural rendering" in call_kwargs["query"]


def test_arxiv_scraper_sets_topic_id_on_article():
    from unittest.mock import MagicMock
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    from src.infrastructure.external.arxiv_client import ArxivEntry
    scraper = ArxivScraper(topic_id="test-topic-uuid", fetch_pdf=False)
    entry = ArxivEntry(
        url="https://arxiv.org/abs/2601.00001v1",
        pdf_url=None, title="Test", abstract="Abs.",
        published=datetime.now(timezone.utc).isoformat(),
        authors=["Alice"], arxiv_id="2601.00001",
    )
    article = scraper._build_article(entry)
    assert article.topic_id == "test-topic-uuid"


# ── 429 retry ─────────────────────────────────────────────────────────────

@responses.activate
def test_discover_retries_on_429_and_succeeds():
    from unittest.mock import patch
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query", status=429)
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry()), status=200)
    with patch("time.sleep"):
        tasks = ArxivScraper(fetch_pdf=False).discover()
    assert len(tasks) == 1


@responses.activate
def test_discover_returns_empty_after_exhausting_retries_on_429():
    from unittest.mock import patch
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    for _ in range(4):
        responses.add(responses.GET, "https://export.arxiv.org/api/query", status=429)
    with patch("time.sleep"):
        tasks = ArxivScraper(fetch_pdf=False).discover()
    assert tasks == []


@responses.activate
def test_discover_handles_entry_with_missing_summary():
    from src.ingestion.scrapers.arxiv_scraper import ArxivScraper
    entry_xml = (
        f"<entry>"
        f"<id>http://arxiv.org/abs/2401.00004v1</id>"
        f"<title>Minimal Entry</title>"
        f"<summary></summary>"
        f"<published>{RECENT}</published>"
        f"</entry>"
    )
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(entry_xml), status=200)
    tasks = ArxivScraper(fetch_pdf=False).discover()
    assert len(tasks) == 1
    article = tasks[0].execute()
    assert article.title == "Minimal Entry"
    assert article.content == ""
