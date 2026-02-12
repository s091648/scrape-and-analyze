## ADDED Requirements

### Requirement: Structured Logging
The system SHALL emit logs in structured JSON format.

#### Scenario: Log format
- **WHEN** emitting a log entry
- **THEN** the system outputs JSON with: timestamp, level, event, correlation_id, and context fields

#### Scenario: Article scraped event
- **WHEN** an article is successfully scraped
- **THEN** the system logs event="article_scraped" with source, article_id, content_length

#### Scenario: Analysis completed event
- **WHEN** an article is successfully analyzed
- **THEN** the system logs event="analysis_completed" with article_id, input_tokens, output_tokens, llm_latency_ms

#### Scenario: Error event
- **WHEN** an error occurs
- **THEN** the system logs level="error" with exception_type, exception_message, and relevant context

### Requirement: Correlation ID in Logs
The system SHALL include correlation_id in all log entries for traceability.

#### Scenario: Include correlation ID
- **WHEN** logging any event during an execution
- **THEN** the log entry includes the correlation_id of the current execution

#### Scenario: Log query by correlation ID
- **WHEN** investigating an issue
- **THEN** users can filter logs by correlation_id to trace a single execution

### Requirement: Log Output Configuration
The system SHALL output logs to stdout for Railway capture.

#### Scenario: PYTHONUNBUFFERED enabled
- **WHEN** the container starts
- **THEN** PYTHONUNBUFFERED=1 ensures immediate log output

#### Scenario: Railway log integration
- **WHEN** logs are emitted to stdout
- **THEN** Railway captures and displays logs in the dashboard

### Requirement: Grafana Cloud Integration
The system SHALL support forwarding logs to Grafana Cloud.

#### Scenario: Loki log forwarding
- **WHEN** Grafana Cloud is configured
- **THEN** Railway logs can be forwarded to Grafana Loki for aggregation

#### Scenario: Log-based metrics
- **WHEN** analyzing logs in Grafana
- **THEN** users can create metrics from log events (e.g., articles_scraped_total)

### Requirement: Key Metrics Logging
The system SHALL log key metrics for monitoring dashboards.

#### Scenario: Scrape metrics
- **WHEN** an execution completes
- **THEN** the system logs: total_articles_scraped, articles_by_source, failures_count

#### Scenario: LLM metrics
- **WHEN** an execution completes
- **THEN** the system logs: total_tokens_used, avg_llm_latency_ms, analysis_count

#### Scenario: Execution metrics
- **WHEN** an execution completes
- **THEN** the system logs: execution_duration_seconds, batch_size, timeout_occurred

### Requirement: Alerting Conditions
The system SHALL log events that can trigger Grafana alerts.

#### Scenario: High failure rate alert
- **WHEN** more than 5 failures occur in a single execution
- **THEN** the system logs level="warning" with alert_condition="high_failure_rate"

#### Scenario: Execution timeout alert
- **WHEN** execution timeout is triggered
- **THEN** the system logs level="warning" with alert_condition="execution_timeout"

#### Scenario: No execution alert condition
- **WHEN** Grafana detects no scrape logs in 25 hours
- **THEN** Grafana can trigger a "missing execution" alert

### Requirement: Error Tracking
The system SHALL support error tracking integration.

#### Scenario: Sentry integration
- **WHEN** SENTRY_DSN environment variable is set
- **THEN** the system reports uncaught exceptions to Sentry

#### Scenario: Error context
- **WHEN** reporting an error to Sentry
- **THEN** the system includes correlation_id, source, and article_url in error context
