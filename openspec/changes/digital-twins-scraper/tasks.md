## 1. Project Setup

- [ ] 1.1 Initialize Python project with pyproject.toml or requirements.txt
- [ ] 1.2 Create src/ directory structure as defined in design (main.py, config.py, database.py, models/, scrapers/, analyzers/, utils/)
- [ ] 1.3 Create Dockerfile with PYTHONUNBUFFERED=1
- [ ] 1.4 Create railway.toml for build configuration
- [ ] 1.5 Create .env.example with required environment variables
- [ ] 1.6 Set up pytest and test directory structure (tests/unit/, tests/integration/)

## 2. Database Layer

- [ ] 2.1 Implement database.py with SQLAlchemy engine using NullPool
- [ ] 2.2 Create Article model (src/models/article.py) with all fields and constraints
- [ ] 2.3 Create Analysis model (src/models/analysis.py) with foreign key to Article
- [ ] 2.4 Create FailedTask model (src/models/failed_task.py)
- [ ] 2.5 Create database migration scripts (Alembic or raw SQL)
- [ ] 2.6 Write unit tests for models
- [ ] 2.7 Implement helper functions: has_analysis(), find_missing_analyses(), find_recent_failures()

## 3. Utilities

- [ ] 3.1 Implement src/utils/logging.py with structlog JSON configuration
- [ ] 3.2 Implement src/utils/sanitizer.py with sanitize_content() function
- [ ] 3.3 Implement URL hash generation function (SHA-256)
- [ ] 3.4 Write unit tests for sanitizer (HTML removal, truncation, empty content)
- [ ] 3.5 Write unit tests for URL hash generation

## 4. RSS Scraper

- [ ] 4.1 Create BaseScraper abstract class (src/scrapers/base.py)
- [ ] 4.2 Implement RssScraper class (src/scrapers/rss_scraper.py)
- [ ] 4.3 Implement RSS feed parsing with feedparser or similar library
- [ ] 4.4 Implement article content extraction from URLs
- [ ] 4.5 Implement Digital Twins keyword filtering
- [ ] 4.6 Implement rate limiting (1 second between requests)
- [ ] 4.7 Configure RSS sources (TechCrunch, VentureBeat, IoT World Today)
- [ ] 4.8 Write unit tests for RSS parsing
- [ ] 4.9 Write unit tests for keyword filtering

## 5. arXiv API Scraper

- [ ] 5.1 Implement ArxivScraper class (src/scrapers/arxiv_scraper.py)
- [ ] 5.2 Implement arXiv API query construction with search terms
- [ ] 5.3 Implement paper metadata extraction (title, abstract, authors, etc.)
- [ ] 5.4 Implement date filtering (last 7 days)
- [ ] 5.5 Implement result limit (max 100 papers)
- [ ] 5.6 Write unit tests for arXiv API response parsing

## 6. Blog Scraper

- [ ] 6.1 Implement BlogScraper class (src/scrapers/blog_scraper.py)
- [ ] 6.2 Create blog-specific CSS selector configurations
- [ ] 6.3 Implement article link discovery from listing pages
- [ ] 6.4 Implement blog content extraction
- [ ] 6.5 Implement robots.txt checking
- [ ] 6.6 Configure blog sources (NVIDIA, Siemens, AWS IoT, Azure IoT)
- [ ] 6.7 Write unit tests for blog parsing with mock HTML

## 7. LLM Analyzer

- [ ] 7.1 Create LLMProvider abstract class (src/analyzers/llm_provider.py)
- [ ] 7.2 Create AnalysisResult dataclass
- [ ] 7.3 Implement ClaudeProvider class (src/analyzers/claude.py)
- [ ] 7.4 Create analysis prompt template (src/prompts/analysis.txt)
- [ ] 7.5 Implement JSON response parsing and validation
- [ ] 7.6 Implement token usage tracking
- [ ] 7.7 Implement retry logic with tenacity (3 retries, exponential backoff)
- [ ] 7.8 Write unit tests with mocked LLM responses

## 8. Main Execution Flow

- [ ] 8.1 Implement src/main.py CLI entry point with argparse (daily/weekly/remediate)
- [ ] 8.2 Implement run_daily_scrape() function with ThreadPoolExecutor
- [ ] 8.3 Implement run_weekly_scrape() function
- [ ] 8.4 Implement auto_redrive_recent_failures() function
- [ ] 8.5 Implement process_article() with transaction handling
- [ ] 8.6 Implement process_article_safe() with error recording
- [ ] 8.7 Implement batch size limiting (max 50 articles)
- [ ] 8.8 Implement execution timeout (50 minutes)
- [ ] 8.9 Implement graceful shutdown on timeout
- [ ] 8.10 Implement correlation_id generation and propagation

## 9. Error Handling

- [ ] 9.1 Implement record_failure() function
- [ ] 9.2 Implement remediate command for manual retry of all unresolved failures
- [ ] 9.3 Implement scan_missing_analyses() for zombie record detection
- [ ] 9.4 Write integration tests for failure recording
- [ ] 9.5 Write integration tests for auto-redrive

## 10. Configuration

- [ ] 10.1 Implement src/config.py with environment variable loading
- [ ] 10.2 Define source configurations (RSS URLs, blog URLs, selectors)
- [ ] 10.3 Implement source loading by schedule_type (daily/weekly)
- [ ] 10.4 Add configuration validation at startup

## 11. Integration Testing

- [ ] 11.1 Create docker-compose.yml for local PostgreSQL
- [ ] 11.2 Write integration test for full scrape-analyze flow
- [ ] 11.3 Write integration test for transaction atomicity (rollback on failure)
- [ ] 11.4 Write integration test for deduplication
- [ ] 11.5 Write integration test for connection cleanup

## 12. Observability

- [ ] 12.1 Add structlog configuration with JSON output
- [ ] 12.2 Add correlation_id to all log entries
- [ ] 12.3 Add execution summary logging (totals, duration, failures)
- [ ] 12.4 Add LLM metrics logging (tokens, latency)
- [ ] 12.5 Add Sentry integration (optional, based on SENTRY_DSN)

## 13. Deployment

- [ ] 13.1 Test Docker build locally
- [ ] 13.2 Create Railway project
- [ ] 13.3 Add PostgreSQL database in Railway
- [ ] 13.4 Configure environment variables in Railway
- [ ] 13.5 Create daily-scraper Cron Job (0 8 * * *)
- [ ] 13.6 Create weekly-scraper Cron Job (0 8 * * 1)
- [ ] 13.7 Run database migrations in production
- [ ] 13.8 Verify first successful execution
- [ ] 13.9 Set up Grafana Cloud log forwarding (optional)
