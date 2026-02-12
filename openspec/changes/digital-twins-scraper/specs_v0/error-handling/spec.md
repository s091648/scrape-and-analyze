## ADDED Requirements

### Requirement: Graceful Degradation for Scraper Failures
The system SHALL continue processing when individual scraper sources fail.

#### Scenario: Single source failure
- **WHEN** one RSS feed or blog source fails
- **THEN** the system logs the error with correlation_id and continues processing other sources
- **Acceptance Criteria**:
  - **Tool**: pytest + responses + caplog
  - **Validation**: Integration test with one mocked 500 response, verify other sources processed
  - **Assertion**: `assert len(successful_articles) > 0` and `assert "error" in caplog.text.lower()`

#### Scenario: Multiple source failures
- **WHEN** multiple sources fail in a single execution
- **THEN** the system logs each failure and processes all successful sources
- **Acceptance Criteria**:
  - **Tool**: pytest + responses + caplog
  - **Validation**: Integration test with 3/5 sources failing, verify 2 sources still processed
  - **Assertion**: `assert caplog.text.count("error") >= 3` and `assert len(results) == 2`

### Requirement: DynamoDB Write Retry
The system SHALL retry DynamoDB write operations on transient failures.

#### Scenario: Transient write failure
- **WHEN** a DynamoDB write fails due to transient error
- **THEN** the system retries up to 3 times with exponential backoff
- **Acceptance Criteria**:
  - **Tool**: pytest + moto + unittest.mock
  - **Validation**: Unit test mocks first 2 writes to fail, third succeeds, verify 3 attempts made
  - **Assertion**: `assert mock_put_item.call_count == 3`

#### Scenario: Persistent write failure
- **WHEN** a DynamoDB write fails after 3 retries
- **THEN** the system logs the error and continues processing other articles
- **Acceptance Criteria**:
  - **Tool**: pytest + moto + caplog
  - **Validation**: Unit test mocks all writes to fail, verify error logged and no exception raised
  - **Assertion**: `assert "failed after 3 retries" in caplog.text.lower()` and no exception

### Requirement: DynamoDB Streams Retry
The system SHALL leverage DynamoDB Streams automatic retry for Analyzer Lambda failures.

#### Scenario: Analyzer Lambda failure
- **WHEN** Analyzer Lambda fails to process a Stream event
- **THEN** Event Source Mapping automatically retries up to 3 times
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies Event Source Mapping has MaximumRetryAttempts: 3
  - **Assertion**: `template.hasResourceProperties("AWS::Lambda::EventSourceMapping", {"MaximumRetryAttempts": 3})`

#### Scenario: Max retries exceeded
- **WHEN** Analyzer Lambda fails after 3 retries
- **THEN** the failed record is sent to the Dead Letter Queue
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion + LocalStack E2E
  - **Validation**: CDK test verifies DestinationConfig.OnFailure points to SQS; E2E test verifies message in DLQ
  - **Assertion (CDK)**: `template.hasResourceProperties("AWS::Lambda::EventSourceMapping", {"DestinationConfig": {"OnFailure": {"Destination": Match.anyValue()}}})`

### Requirement: Dead Letter Queue (DLQ)
The system SHALL send failed Stream events to an SQS Dead Letter Queue for manual investigation.

#### Scenario: DLQ message storage
- **WHEN** a Stream event fails all retry attempts
- **THEN** the message is stored in DLQ for 14 days
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies SQS queue has MessageRetentionPeriod: 1209600 (14 days in seconds)
  - **Assertion**: `template.hasResourceProperties("AWS::SQS::Queue", {"MessageRetentionPeriod": 1209600})`

#### Scenario: DLQ monitoring
- **WHEN** a message enters the DLQ
- **THEN** CloudWatch Alarm triggers and sends SNS email notification
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies CloudWatch Alarm on ApproximateNumberOfMessagesVisible > 0
  - **Assertion**: `template.hasResourceProperties("AWS::CloudWatch::Alarm", {"MetricName": "ApproximateNumberOfMessagesVisible", "Threshold": 0, "ComparisonOperator": "GreaterThanThreshold"})`

### Requirement: Rate Limit Handling
The system SHALL implement exponential backoff when encountering rate limits.

#### Scenario: LLM API rate limit
- **WHEN** LLM API returns rate limit error (429)
- **THEN** the system waits with exponential backoff before retrying
- **Acceptance Criteria**:
  - **Tool**: pytest + responses + unittest.mock
  - **Validation**: Unit test with 429 response verifies exponential sleep times (1s, 2s, 4s)
  - **Assertion**: `assert mock_sleep.call_args_list == [call(1), call(2), call(4)]`

#### Scenario: External API rate limit
- **WHEN** external API (RSS, arXiv) returns rate limit error
- **THEN** the system waits with exponential backoff before retrying
- **Acceptance Criteria**:
  - **Tool**: pytest + responses + unittest.mock
  - **Validation**: Unit test with 429 response verifies backoff pattern
  - **Assertion**: `assert mock_sleep.call_count >= 2`

### Requirement: Correlation ID in Error Logs
The system SHALL include correlation_id in all error log entries for traceability.

#### Scenario: Error logging format
- **WHEN** logging any error
- **THEN** the log entry includes correlation_id, execution_id, source, and error details
- **Acceptance Criteria**:
  - **Tool**: pytest + caplog + json
  - **Validation**: Unit test captures error log, parses as JSON, verifies required fields
  - **Assertion**: `log = json.loads(caplog.records[0].message)` and `assert all(k in log for k in ["correlation_id", "execution_id", "source"])`

#### Scenario: End-to-end tracing
- **WHEN** investigating a failed article
- **THEN** CloudWatch Insights can filter all logs by correlation_id
- **Acceptance Criteria**:
  - **Tool**: E2E test with CloudWatch Logs Insights
  - **Validation**: Query `filter correlation_id = "xxx"` returns all related log entries
  - **Assertion**: Query returns logs from both Scraper and Analyzer Lambda

### Requirement: Partial Success Handling
The system SHALL report partial success when some operations succeed and others fail.

#### Scenario: Mixed results
- **WHEN** some articles are successfully processed and others fail
- **THEN** the system logs a summary with success and failure counts
- **Acceptance Criteria**:
  - **Tool**: pytest + caplog
  - **Validation**: Integration test with 5 articles (3 success, 2 fail) logs summary
  - **Assertion**: `assert "processed: 3" in caplog.text.lower()` and `assert "failed: 2" in caplog.text.lower()`
