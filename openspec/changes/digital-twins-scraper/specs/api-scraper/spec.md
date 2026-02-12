## ADDED Requirements

### Requirement: arXiv API Query
The system SHALL query the arXiv.org API to search for Digital Twins related research papers.

#### Scenario: Successful API query
- **WHEN** the scraper queries arXiv API with search terms
- **THEN** the system retrieves paper entries with title, abstract, authors, published date, and PDF URL

#### Scenario: API rate limit exceeded
- **WHEN** arXiv API returns a 429 rate limit error
- **THEN** the system waits with exponential backoff and retries up to 3 times

#### Scenario: API unavailable
- **WHEN** arXiv API returns an error or times out
- **THEN** the system logs the error and continues with cached results or empty list

### Requirement: arXiv Search Query Construction
The system SHALL construct search queries targeting Digital Twins research.

#### Scenario: Build search query
- **WHEN** querying arXiv API
- **THEN** the system uses search terms: "digital twin" OR "digital twins" in title or abstract fields

#### Scenario: Limit result count
- **WHEN** executing search query
- **THEN** the system limits results to maximum 100 papers per query

#### Scenario: Filter by date
- **WHEN** executing daily search query
- **THEN** the system filters papers published in the last 7 days

### Requirement: arXiv Paper Metadata Extraction
The system SHALL extract structured metadata from arXiv API responses.

#### Scenario: Extract paper metadata
- **WHEN** parsing arXiv API response
- **THEN** the system extracts: arXiv ID, title, abstract, authors list, published date, categories, PDF URL

#### Scenario: Handle missing fields
- **WHEN** a paper entry has missing optional fields (e.g., categories)
- **THEN** the system uses empty defaults and continues processing

### Requirement: arXiv Abstract as Content
The system SHALL use the paper abstract as the article content for LLM analysis.

#### Scenario: Use abstract for analysis
- **WHEN** storing arXiv paper for analysis
- **THEN** the system stores the abstract as the article content field

#### Scenario: Abstract exceeds limit
- **WHEN** the abstract exceeds 50,000 characters
- **THEN** the system truncates and appends "[Content truncated]"

### Requirement: arXiv Deduplication
The system SHALL prevent duplicate arXiv papers using the arXiv ID.

#### Scenario: New paper detected
- **WHEN** a paper with a new arXiv ID is found
- **THEN** the system stores the paper for analysis

#### Scenario: Duplicate paper detected
- **WHEN** a paper with an existing arXiv ID is found
- **THEN** the system skips the paper without error
