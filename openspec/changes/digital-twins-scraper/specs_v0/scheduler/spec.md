## ADDED Requirements

### Requirement: Daily Schedule Rule
The system SHALL trigger Scraper Lambda daily at UTC 08:00 for RSS and API sources.

#### Scenario: Daily trigger
- **WHEN** the clock reaches UTC 08:00 each day
- **THEN** EventBridge triggers Scraper Lambda with {"schedule": "daily"} payload
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies EventBridge Rule with cron(0 8 * * ? *) targeting Scraper Lambda
  - **Assertion**: `template.hasResourceProperties("AWS::Events::Rule", {"ScheduleExpression": "cron(0 8 * * ? *)"})`

#### Scenario: Daily sources processing
- **WHEN** Scraper Lambda receives {"schedule": "daily"}
- **THEN** the system processes TechCrunch RSS, VentureBeat RSS, IoT World Today RSS, and arXiv API
- **Acceptance Criteria**:
  - **Tool**: pytest + unittest.mock
  - **Validation**: Unit test with {"schedule": "daily"} event verifies correct scrapers invoked
  - **Assertion**: `assert mock_rss_scraper.call_count == 3` and `assert mock_arxiv_scraper.call_count == 1`

### Requirement: Weekly Schedule Rule
The system SHALL trigger Scraper Lambda weekly on Monday at UTC 08:00 for blog sources.

#### Scenario: Weekly trigger
- **WHEN** the clock reaches Monday UTC 08:00
- **THEN** EventBridge triggers Scraper Lambda with {"schedule": "weekly"} payload
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies EventBridge Rule with cron(0 8 ? * MON *) targeting Scraper Lambda
  - **Assertion**: `template.hasResourceProperties("AWS::Events::Rule", {"ScheduleExpression": "cron(0 8 ? * MON *)"})`

#### Scenario: Weekly sources processing
- **WHEN** Scraper Lambda receives {"schedule": "weekly"}
- **THEN** the system processes NVIDIA Blog, Siemens Digital Industries, AWS IoT Blog, and Azure IoT Blog
- **Acceptance Criteria**:
  - **Tool**: pytest + unittest.mock
  - **Validation**: Unit test with {"schedule": "weekly"} event verifies blog scrapers invoked
  - **Assertion**: `assert mock_blog_scraper.call_count == 4` (one per blog)

### Requirement: EventBridge Cron Expressions
The system SHALL use valid EventBridge cron expressions for scheduling.

#### Scenario: Daily cron expression
- **WHEN** configuring daily rule
- **THEN** the system uses cron(0 8 * * ? *)
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion + cron validation
  - **Validation**: CDK test verifies exact cron expression string
  - **Assertion**: `assert "cron(0 8 * * ? *)" in stack_template`

#### Scenario: Weekly cron expression
- **WHEN** configuring weekly rule
- **THEN** the system uses cron(0 8 ? * MON *)
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies exact cron expression string
  - **Assertion**: `assert "cron(0 8 ? * MON *)" in stack_template`

### Requirement: Single Lambda Entry Point
The system SHALL use a single Scraper Lambda that handles both daily and weekly schedules.

#### Scenario: Schedule differentiation
- **WHEN** Scraper Lambda receives an event
- **THEN** the system reads the schedule field to determine which sources to process
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test verifies handler reads event["schedule"] and branches accordingly
  - **Assertion**: `assert handler({"schedule": "daily"}) != handler({"schedule": "weekly"})` (different sources processed)

#### Scenario: Source configuration
- **WHEN** adding or removing sources
- **THEN** only the source configuration needs updating, not the Lambda count
- **Acceptance Criteria**:
  - **Tool**: Code review + AWS CDK assertion
  - **Validation**: CDK test verifies only 1 Scraper Lambda function exists; source list is in config
  - **Assertion**: `template.resourceCountIs("AWS::Lambda::Function", 2)` (Scraper + Analyzer only)

### Requirement: Timezone Consideration
The system SHALL execute at a fixed UTC time to simplify monitoring.

#### Scenario: Consistent execution time
- **WHEN** the schedule triggers
- **THEN** execution occurs at UTC 08:00 (Taiwan 16:00) regardless of daylight saving
- **Acceptance Criteria**:
  - **Tool**: Documentation review + AWS CDK assertion
  - **Validation**: Verify cron uses UTC (EventBridge default), documented in design
  - **Assertion**: Cron expression does not include timezone override; design.md mentions "UTC 08:00"

### Requirement: Execution ID Generation
The system SHALL generate a unique execution_id for each scheduled run.

#### Scenario: Execution tracking
- **WHEN** Scraper Lambda is triggered by EventBridge
- **THEN** the system generates a unique execution_id for the entire batch
- **Acceptance Criteria**:
  - **Tool**: pytest + uuid
  - **Validation**: Unit test verifies handler generates valid UUID as execution_id
  - **Assertion**: `uuid.UUID(result["execution_id"])` does not raise ValueError

#### Scenario: Execution ID in logs
- **WHEN** processing articles in a batch
- **THEN** all log entries include the same execution_id
- **Acceptance Criteria**:
  - **Tool**: pytest + caplog
  - **Validation**: Unit test processes 3 articles, verifies all logs have same execution_id
  - **Assertion**: `assert len(set(log["execution_id"] for log in logs)) == 1`
