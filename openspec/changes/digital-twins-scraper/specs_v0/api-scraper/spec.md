## ADDED Requirements

### Requirement: arXiv API Integration
The system SHALL query the arXiv.org API to retrieve Digital Twins related research papers.

#### Scenario: Successful API query
- **WHEN** the scraper queries arXiv API with Digital Twins search terms
- **THEN** the system correctly parses the JSON/XML response and extracts paper metadata
- **Acceptance Criteria**:
  - **Tool**: pytest + responses (HTTP mock)
  - **Validation**: Unit test with mock arXiv API response fixture returns list of Article objects
  - **Assertion**: `assert len(articles) > 0` and `assert all(a.source == "arxiv" for a in articles)`

#### Scenario: Empty API response
- **WHEN** arXiv API returns no results
- **THEN** the system returns an empty list without throwing an error
- **Acceptance Criteria**:
  - **Tool**: pytest + responses
  - **Validation**: Unit test with empty result response returns empty list, no exception
  - **Assertion**: `assert scraper.fetch() == []` and no exception raised

#### Scenario: API response error
- **WHEN** arXiv API returns an error response (4xx, 5xx)
- **THEN** the system logs the error with correlation_id and continues processing other sources
- **Acceptance Criteria**:
  - **Tool**: pytest + responses + caplog (pytest logging capture)
  - **Validation**: Unit test with 500 response logs error with correlation_id, returns empty list
  - **Assertion**: `assert "correlation_id" in caplog.text` and `assert "arxiv" in caplog.text`

### Requirement: Article ID Generation
The system SHALL generate deterministic article IDs using SHA-256 hash of the URL.

#### Scenario: Same URL produces same ID
- **WHEN** the same URL is processed multiple times
- **THEN** the system generates identical article_id values
- **Acceptance Criteria**:
  - **Tool**: pytest + hashlib
  - **Validation**: Unit test calls generate_article_id() twice with same URL, compares results
  - **Assertion**: `assert generate_article_id(url) == generate_article_id(url)`

#### Scenario: Different URLs produce different IDs
- **WHEN** different URLs are processed
- **THEN** the system generates unique article_id values
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test with 100 different URLs produces 100 unique IDs
  - **Assertion**: `assert len(set(ids)) == len(urls)`

### Requirement: Content Sanitization
The system SHALL sanitize API response content before storage.

#### Scenario: Content cleaning from API
- **WHEN** content is received from arXiv API
- **THEN** the system applies HTML to text conversion and truncation (max 30KB)
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test with arXiv abstract containing LaTeX/HTML returns clean text under 30KB
  - **Assertion**: `assert "<" not in result` and `assert len(result.encode()) <= 30000`

### Requirement: Rate Limiting for API Calls
The system SHALL implement rate limiting to respect API usage policies.

#### Scenario: Sequential API requests
- **WHEN** making multiple requests to arXiv API
- **THEN** the system waits an appropriate interval between requests
- **Acceptance Criteria**:
  - **Tool**: pytest + unittest.mock + time
  - **Validation**: Integration test with 3 API calls verifies sleep called between each
  - **Assertion**: `assert mock_sleep.call_count >= 2`
