## ADDED Requirements

### Requirement: Article Storage
The system SHALL store scraped articles in PostgreSQL with full metadata.

#### Scenario: Store new article
- **WHEN** a new article is scraped
- **THEN** the system stores: URL, URL hash, source, title, content, published date, scraped timestamp, metadata, correlation ID

#### Scenario: Generate URL hash
- **WHEN** storing an article
- **THEN** the system generates a SHA-256 hash of the URL as the unique identifier

#### Scenario: Storage transaction
- **WHEN** storing article and analysis together
- **THEN** the system uses a single database transaction for atomicity

### Requirement: Article Deduplication
The system SHALL prevent duplicate articles using URL hash.

#### Scenario: New article URL
- **WHEN** an article with a new URL hash is submitted
- **THEN** the system stores the article successfully

#### Scenario: Duplicate article URL
- **WHEN** an article with an existing URL hash is submitted
- **THEN** the system skips the article and checks if analysis exists

#### Scenario: Duplicate without analysis
- **WHEN** an existing article has no corresponding analysis
- **THEN** the system triggers analysis for the existing article

### Requirement: Analysis Storage
The system SHALL store LLM analysis results linked to articles.

#### Scenario: Store analysis results
- **WHEN** LLM analysis completes successfully
- **THEN** the system stores: article ID, correlation ID, tags, pain points, insights, innovations, analyzed timestamp, model used, token counts

#### Scenario: One analysis per article
- **WHEN** analysis is stored for an article
- **THEN** the system enforces unique constraint on article_id

#### Scenario: Analysis update
- **WHEN** re-analyzing an existing article
- **THEN** the system overwrites the previous analysis

### Requirement: Failed Task Recording
The system SHALL record failed tasks for later remediation.

#### Scenario: Record scrape failure
- **WHEN** an article scrape fails after retries
- **THEN** the system stores: task type, article URL, exception details, timestamp

#### Scenario: Record analysis failure
- **WHEN** an LLM analysis fails after retries
- **THEN** the system stores: task type, article ID, exception details, timestamp

#### Scenario: Mark task resolved
- **WHEN** a failed task is successfully remediated
- **THEN** the system updates resolved=true and resolved_at timestamp

### Requirement: Database Connection Management
The system SHALL manage database connections efficiently for Railway's limits.

#### Scenario: Connection pooling disabled
- **WHEN** connecting to PostgreSQL
- **THEN** the system uses NullPool to create connections on-demand

#### Scenario: Session cleanup
- **WHEN** an article processing completes
- **THEN** the system calls session.remove() to release the connection

#### Scenario: Connection limit respect
- **WHEN** running concurrent operations
- **THEN** the system ensures total connections stay below Railway's limit (~20)

### Requirement: Query Support
The system SHALL support querying stored data for analysis and remediation.

#### Scenario: Find articles without analysis
- **WHEN** running remediation scan
- **THEN** the system queries articles that have no corresponding analysis record

#### Scenario: Find recent failures
- **WHEN** running auto-redrive
- **THEN** the system queries failed_tasks where resolved=false and failed_at within 24 hours

#### Scenario: Query by source
- **WHEN** filtering articles
- **THEN** the system supports filtering by source name
