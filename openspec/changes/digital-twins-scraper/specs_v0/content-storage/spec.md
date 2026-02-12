## ADDED Requirements

### Requirement: ArticlesTable Schema
The system SHALL store scraped articles in a DynamoDB table with article_id (SHA-256 hash of URL) as the primary key.

#### Scenario: Article storage structure
- **WHEN** storing a scraped article
- **THEN** the system stores source, url, title, content (cleaned text), published_at, scraped_at, metadata, and correlation_id
- **Acceptance Criteria**:
  - **Tool**: pytest + moto (AWS mock) or LocalStack
  - **Validation**: Integration test writes article and reads back, verifying all fields present
  - **Assertion**: `assert item["source"]["S"]` and `assert item["url"]["S"]` and `assert item["correlation_id"]["S"]`

#### Scenario: Primary key generation
- **WHEN** creating an article record
- **THEN** the system generates article_id using SHA-256 hash of the URL
- **Acceptance Criteria**:
  - **Tool**: pytest + hashlib
  - **Validation**: Unit test verifies article_id matches SHA-256 hex digest of URL
  - **Assertion**: `assert article.article_id == hashlib.sha256(url.encode()).hexdigest()`

### Requirement: Deduplication via Conditional Write
The system SHALL use DynamoDB Conditional Write to prevent duplicate article storage.

#### Scenario: New article
- **WHEN** writing an article with a new article_id
- **THEN** the system successfully stores the article
- **Acceptance Criteria**:
  - **Tool**: pytest + moto/LocalStack
  - **Validation**: Integration test writes new article, verifies 200 response and item exists
  - **Assertion**: `assert response["ResponseMetadata"]["HTTPStatusCode"] == 200`

#### Scenario: Duplicate article
- **WHEN** writing an article with an existing article_id
- **THEN** the Conditional Write fails and the system logs the duplicate, continuing to process other articles
- **Acceptance Criteria**:
  - **Tool**: pytest + moto/LocalStack + botocore.exceptions
  - **Validation**: Integration test writes same article twice, second write raises ConditionalCheckFailedException
  - **Assertion**: `with pytest.raises(botocore.exceptions.ClientError) as exc:` and `assert "ConditionalCheckFailedException" in str(exc.value)`

### Requirement: DynamoDB Streams Integration
The system SHALL enable DynamoDB Streams on ArticlesTable to trigger downstream processing.

#### Scenario: Stream event on insert
- **WHEN** a new article is written to ArticlesTable
- **THEN** DynamoDB Streams emits a NEW_IMAGE event to trigger Analyzer Lambda
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion (cdk-assertions) + LocalStack
  - **Validation**: CDK test verifies table has StreamSpecification with NEW_IMAGE; Integration test verifies stream record created
  - **Assertion (CDK)**: `template.hasResourceProperties("AWS::DynamoDB::Table", {"StreamSpecification": {"StreamViewType": "NEW_IMAGE"}})`

#### Scenario: Stream configuration
- **WHEN** configuring DynamoDB Streams
- **THEN** the system sets Stream View Type to NEW_IMAGE and Batch Size to 1
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies Event Source Mapping has BatchSize: 1
  - **Assertion**: `template.hasResourceProperties("AWS::Lambda::EventSourceMapping", {"BatchSize": 1})`

### Requirement: Provisioned Capacity Mode (Free Tier)
The system SHALL use Provisioned Capacity Mode with 15 WCU to stay within AWS Free Tier limits.

#### Scenario: Capacity allocation
- **WHEN** creating ArticlesTable
- **THEN** the system provisions 15 WCU for writes
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies ProvisionedThroughput settings
  - **Assertion**: `template.hasResourceProperties("AWS::DynamoDB::Table", {"ProvisionedThroughput": {"WriteCapacityUnits": 15}})`

#### Scenario: Write throttling prevention
- **WHEN** batch writing articles
- **THEN** the Scraper Lambda implements rate limiting (2 second intervals) to prevent throttling
- **Acceptance Criteria**:
  - **Tool**: pytest + moto + unittest.mock
  - **Validation**: Integration test with 10 articles verifies no ProvisionedThroughputExceededException
  - **Assertion**: No exception raised and `assert mock_sleep.call_count == 9` (N-1 sleeps for N items)

### Requirement: Correlation ID Tracking
The system SHALL store correlation_id with each article for end-to-end tracing.

#### Scenario: Correlation ID generation
- **WHEN** scraping a new article
- **THEN** the system generates and stores a unique correlation_id
- **Acceptance Criteria**:
  - **Tool**: pytest + uuid
  - **Validation**: Unit test verifies correlation_id is valid UUID format
  - **Assertion**: `uuid.UUID(article.correlation_id)` does not raise ValueError

#### Scenario: Correlation ID propagation
- **WHEN** the article triggers downstream processing
- **THEN** the correlation_id is propagated through DynamoDB Streams
- **Acceptance Criteria**:
  - **Tool**: pytest + LocalStack
  - **Validation**: Integration test reads stream record, verifies correlation_id present in NEW_IMAGE
  - **Assertion**: `assert stream_record["dynamodb"]["NewImage"]["correlation_id"]["S"]`
