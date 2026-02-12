## ADDED Requirements

### Requirement: AnalysisTable Schema
The system SHALL store LLM analysis results in a DynamoDB table with article_id as the primary key.

#### Scenario: Analysis storage structure
- **WHEN** storing an analysis result
- **THEN** the system stores article_id (PK), correlation_id, tags, pain_points, insights, innovations, analyzed_at, and model_used
- **Acceptance Criteria**:
  - **Tool**: pytest + moto/LocalStack
  - **Validation**: Integration test writes analysis and reads back, verifying all fields present
  - **Assertion**: `assert item["article_id"]["S"]` and `assert item["tags"]["L"]` and `assert item["model_used"]["S"]`

#### Scenario: Primary key matches ArticlesTable
- **WHEN** storing analysis for an article
- **THEN** the article_id matches the corresponding ArticlesTable record
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test verifies analysis.article_id equals source article's article_id
  - **Assertion**: `assert analysis.article_id == article.article_id`

### Requirement: Idempotent Analysis Storage
The system SHALL use article_id as PK to ensure idempotent writes.

#### Scenario: First analysis for article
- **WHEN** storing the first analysis for an article_id
- **THEN** the system creates a new record
- **Acceptance Criteria**:
  - **Tool**: pytest + moto/LocalStack
  - **Validation**: Integration test writes analysis, verifies item exists with correct values
  - **Assertion**: `assert response["ResponseMetadata"]["HTTPStatusCode"] == 200`

#### Scenario: Duplicate analysis attempt
- **WHEN** storing analysis for an existing article_id
- **THEN** the system overwrites the existing record (no duplicate entries)
- **Acceptance Criteria**:
  - **Tool**: pytest + moto/LocalStack
  - **Validation**: Integration test writes analysis twice with different data, verifies only one item with latest data
  - **Assertion**: `assert table.scan()["Count"] == 1` and `assert item["analyzed_at"]["S"] == second_timestamp`

### Requirement: Analysis-Article Relationship
The system SHALL maintain a one-to-one relationship between articles and their analysis results.

#### Scenario: Query analysis by article
- **WHEN** querying AnalysisTable with an article_id
- **THEN** the system retrieves the analysis using GetItem (1 RCU)
- **Acceptance Criteria**:
  - **Tool**: pytest + moto/LocalStack + botocore stubber
  - **Validation**: Integration test queries by article_id, verifies GetItem used (not Query/Scan)
  - **Assertion**: Verify GetItem API call in CloudWatch or mock

#### Scenario: No GSI required
- **WHEN** designing AnalysisTable
- **THEN** no Global Secondary Index is needed due to article_id as PK
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies table has no GSI defined
  - **Assertion**: `template.resourceCountIs("AWS::DynamoDB::Table", 2)` (only 2 tables, no extra GSI resources)

### Requirement: Provisioned Capacity Mode (Free Tier)
The system SHALL use Provisioned Capacity Mode with 10 WCU/RCU to stay within AWS Free Tier limits.

#### Scenario: Capacity allocation
- **WHEN** creating AnalysisTable
- **THEN** the system provisions 10 WCU and 10 RCU
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies ProvisionedThroughput settings for AnalysisTable
  - **Assertion**: `template.hasResourceProperties("AWS::DynamoDB::Table", {"ProvisionedThroughput": {"WriteCapacityUnits": 10, "ReadCapacityUnits": 10}})`

### Requirement: Model Tracking
The system SHALL track which LLM model was used for each analysis.

#### Scenario: Model recording
- **WHEN** storing analysis results
- **THEN** the system records the model_used field (e.g., "claude-3-5-sonnet")
- **Acceptance Criteria**:
  - **Tool**: pytest + moto/LocalStack
  - **Validation**: Integration test verifies model_used field contains expected model name
  - **Assertion**: `assert item["model_used"]["S"] == "claude-3-5-sonnet-20241022"`

#### Scenario: Model version tracking
- **WHEN** querying historical analyses
- **THEN** the user can identify which model version produced each result
- **Acceptance Criteria**:
  - **Tool**: pytest + moto/LocalStack
  - **Validation**: Integration test with 2 analyses using different models, both model names retrievable
  - **Assertion**: `assert item1["model_used"]["S"] != item2["model_used"]["S"]`

### Requirement: Timestamp Recording
The system SHALL record the analysis timestamp for each result.

#### Scenario: Analysis timestamp
- **WHEN** completing an analysis
- **THEN** the system stores analyzed_at in ISO 8601 format
- **Acceptance Criteria**:
  - **Tool**: pytest + datetime
  - **Validation**: Unit test verifies analyzed_at is valid ISO 8601 timestamp
  - **Assertion**: `datetime.fromisoformat(analysis.analyzed_at)` does not raise ValueError
