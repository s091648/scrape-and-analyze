## ADDED Requirements

### Requirement: Daily Scrape Schedule
The system SHALL execute daily scraping via Railway Cron Job.

#### Scenario: Daily cron trigger
- **WHEN** Railway Cron Job triggers at 08:00 UTC daily
- **THEN** the system executes with schedule_type="daily"

#### Scenario: Daily sources selection
- **WHEN** running daily schedule
- **THEN** the system processes RSS sources: TechCrunch, VentureBeat, IoT World Today, and arXiv API

### Requirement: Weekly Scrape Schedule
The system SHALL execute weekly scraping via Railway Cron Job.

#### Scenario: Weekly cron trigger
- **WHEN** Railway Cron Job triggers at 08:00 UTC on Monday
- **THEN** the system executes with schedule_type="weekly"

#### Scenario: Weekly sources selection
- **WHEN** running weekly schedule
- **THEN** the system processes blog sources: NVIDIA, Siemens, AWS IoT, Azure IoT

### Requirement: Execution Time Management
The system SHALL manage execution time to prevent timeouts.

#### Scenario: Maximum execution time
- **WHEN** execution exceeds 50 minutes
- **THEN** the system logs a warning and gracefully shuts down

#### Scenario: Batch size limiting
- **WHEN** more than 50 articles are discovered
- **THEN** the system processes only the first 50 and logs truncation warning

#### Scenario: Graceful shutdown
- **WHEN** shutdown is triggered
- **THEN** the system completes current article processing before exiting

### Requirement: Auto-Redrive on Startup
The system SHALL automatically retry recent failures on each execution.

#### Scenario: Redrive recent failures
- **WHEN** scraper starts execution
- **THEN** the system queries and retries failed_tasks from the last 24 hours

#### Scenario: Successful redrive
- **WHEN** a failed task succeeds on retry
- **THEN** the system marks the task as resolved

#### Scenario: Redrive failure
- **WHEN** a failed task fails again on retry
- **THEN** the system logs the error but does not update the failed_task record

### Requirement: Concurrent Processing
The system SHALL process articles concurrently within a single execution.

#### Scenario: ThreadPoolExecutor usage
- **WHEN** processing multiple articles
- **THEN** the system uses ThreadPoolExecutor with max_workers=3

#### Scenario: Concurrent LLM calls
- **WHEN** multiple articles are being analyzed
- **THEN** the system makes up to 3 concurrent LLM API calls

#### Scenario: Timeout during concurrent processing
- **WHEN** execution timeout is reached during concurrent processing
- **THEN** the system cancels pending futures and exits gracefully

### Requirement: Correlation ID Tracking
The system SHALL assign correlation IDs to track processing sessions.

#### Scenario: Generate correlation ID
- **WHEN** a new scrape execution starts
- **THEN** the system generates a unique UUID as correlation_id

#### Scenario: Propagate correlation ID
- **WHEN** processing articles in an execution
- **THEN** the system includes correlation_id in all stored records and logs

#### Scenario: Trace by correlation ID
- **WHEN** querying logs or database
- **THEN** users can filter by correlation_id to see all records from one execution
