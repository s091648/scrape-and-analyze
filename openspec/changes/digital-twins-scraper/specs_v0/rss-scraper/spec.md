## ADDED Requirements

### Requirement: RSS Feed Parsing
The system SHALL parse RSS feeds from TechCrunch, VentureBeat, and IoT World Today to extract Digital Twins related articles.

#### Scenario: Successful RSS parsing
- **WHEN** the scraper fetches a valid RSS feed
- **THEN** the system extracts title, content, url, and published_at for each article
- **Acceptance Criteria**:
  - **Tool**: pytest + feedparser
  - **Validation**: Unit test with mock RSS XML fixture returns Article objects with all required fields non-empty
  - **Assertion**: `assert article.title and article.url and article.content and article.published_at`

#### Scenario: RSS format error
- **WHEN** the RSS feed contains malformed XML
- **THEN** the system throws a ParseError with source information and continues processing other sources
- **Acceptance Criteria**:
  - **Tool**: pytest + pytest.raises
  - **Validation**: Unit test with malformed XML input raises `ParseError` with source name in exception message
  - **Assertion**: `with pytest.raises(ParseError, match="techcrunch")`

### Requirement: HTML to Text Conversion
The system SHALL convert raw HTML content to plain text while preserving paragraph structure.

#### Scenario: Successful HTML conversion
- **WHEN** raw HTML is received from RSS feed
- **THEN** the system removes script, style, nav, footer, and aside tags and converts block elements to newlines
- **Acceptance Criteria**:
  - **Tool**: pytest + BeautifulSoup
  - **Validation**: Unit test with HTML containing `<p>`, `<div>`, `<h1>` tags outputs text with `\n` separators
  - **Assertion**: `assert "\n" in sanitize_content("<p>A</p><p>B</p>")` and `assert "A\nB" in result`

#### Scenario: Script and style removal
- **WHEN** HTML contains script or style tags
- **THEN** the system removes these tags completely before text extraction
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test with `<script>alert('xss')</script>` in HTML returns text without "alert" or "xss"
  - **Assertion**: `assert "alert" not in sanitize_content(html_with_script)`

### Requirement: Content Truncation
The system SHALL truncate content to a maximum of 30,000 characters to comply with Free Tier WCU limits.

#### Scenario: Content exceeds limit
- **WHEN** cleaned text content exceeds 30,000 characters
- **THEN** the system truncates to 30,000 characters and appends "[Content truncated]"
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test with 50,000 character input returns exactly 30,000 chars + truncation marker
  - **Assertion**: `assert len(result) == 30000 + len("\n[Content truncated]")` and `assert result.endswith("[Content truncated]")`

#### Scenario: Content within limit
- **WHEN** cleaned text content is under 30,000 characters
- **THEN** the system stores the full content without modification
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test with 10,000 character input returns identical content
  - **Assertion**: `assert result == original_content` and `"[Content truncated]" not in result`

### Requirement: Rate Limiting for DynamoDB Writes
The system SHALL implement rate limiting to avoid exceeding Free Tier Provisioned Capacity.

#### Scenario: Sequential article writes
- **WHEN** writing multiple articles to DynamoDB
- **THEN** the system waits 2 seconds between each write operation
- **Acceptance Criteria**:
  - **Tool**: pytest + unittest.mock (time.sleep mock)
  - **Validation**: Integration test verifies `time.sleep(2)` called between writes
  - **Assertion**: `mock_sleep.assert_called_with(2)` and `assert mock_sleep.call_count == len(articles) - 1`

### Requirement: User-Agent Configuration
The system SHALL set a reasonable User-Agent header for all HTTP requests.

#### Scenario: HTTP request headers
- **WHEN** making a request to an RSS feed
- **THEN** the system includes a descriptive User-Agent header
- **Acceptance Criteria**:
  - **Tool**: pytest + responses (HTTP mock library)
  - **Validation**: Unit test captures request headers and verifies User-Agent is set
  - **Assertion**: `assert "User-Agent" in request.headers` and `assert "Digital-Twins-Scraper" in request.headers["User-Agent"]`

### Requirement: Robots.txt Compliance
The system SHALL respect robots.txt directives from target websites.

#### Scenario: Robots.txt check
- **WHEN** accessing a new source
- **THEN** the system checks and respects robots.txt directives
- **Acceptance Criteria**:
  - **Tool**: pytest + robotparser (urllib.robotparser)
  - **Validation**: Unit test with mock robots.txt disallowing path returns False from can_fetch()
  - **Assertion**: `assert scraper.can_access(blocked_url) == False`
