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


def test_fetch_pdf_is_true_by_default():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    assert ArxivScraper()._fetch_pdf is True


def test_respects_max_results():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    assert ArxivScraper(max_results=50)._max_results == 50


def test_builds_query_contains_digital_twin_terms():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    q = ArxivScraper()._build_query()
    assert "digital" in q.lower() or "twin" in q.lower()


@responses.activate
def test_discover_returns_one_job_per_entry():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry()), status=200)
    jobs = ArxivScraper(fetch_pdf=False).discover()
    assert len(jobs) == 1
    assert jobs[0].url == "http://arxiv.org/abs/2401.00001v1"
    assert jobs[0].source == "arxiv"


@responses.activate
def test_discover_returns_empty_on_api_error():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query", status=500)
    assert ArxivScraper().discover() == []


@responses.activate
def test_discover_filters_old_papers():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(published=old)), status=200)
    assert ArxivScraper(days_back=7).discover() == []


@responses.activate
def test_fetch_returns_article_with_abstract_when_fetch_pdf_false():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(summary="Short abstract.")), status=200)
    scraper = ArxivScraper(fetch_pdf=False)
    jobs = scraper.discover()
    article = scraper.fetch(jobs[0])
    assert article is not None
    assert article.content == "Short abstract."
    assert article.source == "arxiv"
    assert article.extra["pdf_available"] is False


@responses.activate
def test_fetch_extracts_authors():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(authors=["Alice", "Bob"])), status=200)
    scraper = ArxivScraper(fetch_pdf=False)
    jobs = scraper.discover()
    article = scraper.fetch(jobs[0])
    # authors is now a top-level field in ScrapedArticle
    assert article.authors == ["Alice", "Bob"]


@responses.activate
def test_fetch_falls_back_to_abstract_when_pdf_fails():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00002", summary="Fallback.")), status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00002v1", status=404)
    scraper = ArxivScraper(fetch_pdf=True)
    jobs = scraper.discover()
    article = scraper.fetch(jobs[0])
    assert article.content == "Fallback."
    assert article.extra["pdf_available"] is False


@responses.activate
def test_fetch_uses_sections_and_sets_pdf_available_true():
    from unittest.mock import patch
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00003", summary="Short abstract.")),
                  status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00003v1",
                  body=b"%PDF-1.4 fake", status=200)
    with patch("src.infrastructure.collection.parsers.pdf_parser.PdfParser.parse",
               return_value="Full PDF text."), \
         patch("src.infrastructure.collection.parsers.pdf_parser.PdfParser.extract_sections",
               return_value={"introduction": "Intro text.", "conclusion": "Conclusion."}):
        scraper = ArxivScraper(fetch_pdf=True)
        jobs = scraper.discover()
        article = scraper.fetch(jobs[0])
    assert article.extra["pdf_available"] is True
    assert article.content == "Short abstract."
    assert article.extra["sections"] == {"introduction": "Intro text.", "conclusion": "Conclusion."}


@responses.activate
def test_fetch_strips_null_bytes_from_sections():
    from unittest.mock import patch
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry(paper_id="2401.00009", summary="Abstract.")),
                  status=200)
    responses.add(responses.GET, "http://arxiv.org/pdf/2401.00009v1",
                  body=b"%PDF-1.4 fake", status=200)
    with patch("src.infrastructure.collection.parsers.pdf_parser.PdfParser.parse",
               return_value="text with \x00 null"), \
         patch("src.infrastructure.collection.parsers.pdf_parser.PdfParser.extract_sections",
               return_value={"introduction": "Hello \x00 world."}):
        scraper = ArxivScraper(fetch_pdf=True)
        jobs = scraper.discover()
        article = scraper.fetch(jobs[0])
    assert "\x00" not in article.extra["sections"].get("introduction", "")


def test_arxiv_scraper_uses_selector_config_keywords():
    from unittest.mock import MagicMock
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
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


def test_arxiv_scraper_sets_topic_id_on_job():
    from unittest.mock import MagicMock
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    from src.infrastructure.collection.clients.arxiv_client import ArxivEntry
    scraper = ArxivScraper(topic_id="test-topic-uuid", fetch_pdf=False)
    entry = ArxivEntry(
        url="https://arxiv.org/abs/2601.00001v1",
        pdf_url=None, title="Test", abstract="Abs.",
        published=datetime.now(timezone.utc).isoformat(),
        authors=["Alice"], arxiv_id="2601.00001",
    )
    jobs = scraper.discover()
    # discover() returns a list, so access the first element
    assert str(jobs[0].topic_id) == "test-topic-uuid"


@responses.activate
def test_discover_retries_on_429_and_succeeds():
    from unittest.mock import patch
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    responses.add(responses.GET, "https://export.arxiv.org/api/query", status=429)
    responses.add(responses.GET, "https://export.arxiv.org/api/query",
                  body=_atom(_entry()), status=200)
    with patch("time.sleep"):
        jobs = ArxivScraper(fetch_pdf=False).discover()
    assert len(jobs) == 1


@responses.activate
def test_discover_returns_empty_after_exhausting_retries_on_429():
    from unittest.mock import patch
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    for _ in range(4):
        responses.add(responses.GET, "https://export.arxiv.org/api/query", status=429)
    with patch("time.sleep"):
        jobs = ArxivScraper(fetch_pdf=False).discover()
    assert jobs == []


@responses.activate
def test_discover_handles_entry_with_missing_summary():
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
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
    scraper = ArxivScraper(fetch_pdf=False)
    jobs = scraper.discover()
    assert len(jobs) == 1
    # Note: arxiv_scraper uses arxiv_id (or url) as title, not the <title> field
    # The title in ScrapedArticle comes from job.metadata.get("arxiv_id", job.url)
    article = scraper.fetch(jobs[0])
    # Since there's no arxiv_id in the entry, title defaults to URL
    assert article.title == "http://arxiv.org/abs/2401.00004v1"