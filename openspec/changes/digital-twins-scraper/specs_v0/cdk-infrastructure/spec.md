## ADDED Requirements

### Requirement: Monorepo Project Structure
The system SHALL organize CDK and Lambda code in a monorepo structure.

#### Scenario: Directory layout
- **WHEN** setting up the project
- **THEN** the system creates cdk/, lambda/, tests/, and .github/ directories
- **Acceptance Criteria**:
  - **Tool**: Filesystem check + pytest
  - **Validation**: Test verifies expected directories exist
  - **Assertion**: `assert all(Path(d).exists() for d in ["cdk", "lambda", "tests", ".github"])`

#### Scenario: CDK constructs separation
- **WHEN** organizing CDK code
- **THEN** the system creates separate construct files for scraper-lambda, analyzer-lambda, dynamodb-tables, and dlq
- **Acceptance Criteria**:
  - **Tool**: Filesystem check
  - **Validation**: Verify construct files exist in cdk/lib/constructs/
  - **Assertion**: `assert all(Path(f"cdk/lib/constructs/{f}.ts").exists() for f in ["scraper-lambda", "analyzer-lambda", "dynamodb-tables", "dlq"])`

### Requirement: Docker Container Image Deployment
The system SHALL deploy Lambda functions using Docker container images.

#### Scenario: Lambda image build
- **WHEN** building Lambda deployment packages
- **THEN** the system uses Dockerfile in each Lambda directory
- **Acceptance Criteria**:
  - **Tool**: Filesystem check + Docker build test
  - **Validation**: Verify Dockerfiles exist and build successfully
  - **Assertion**: `docker build -t test-scraper lambda/scraper/` exits with code 0

#### Scenario: Cross-platform compatibility
- **WHEN** building on Windows or Mac
- **THEN** Docker ensures consistent Linux environment for Lambda execution
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies Lambda uses DockerImageCode
  - **Assertion**: `template.hasResourceProperties("AWS::Lambda::Function", {"PackageType": "Image"})`

### Requirement: DynamoDB Tables with Streams
The system SHALL create ArticlesTable and AnalysisTable with proper configuration.

#### Scenario: ArticlesTable creation
- **WHEN** deploying infrastructure
- **THEN** CDK creates ArticlesTable with article_id PK, DynamoDB Streams (NEW_IMAGE), and 15 WCU Provisioned Capacity
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies table properties
  - **Assertion**: `template.hasResourceProperties("AWS::DynamoDB::Table", {"KeySchema": [{"AttributeName": "article_id", "KeyType": "HASH"}], "StreamSpecification": {"StreamViewType": "NEW_IMAGE"}, "ProvisionedThroughput": {"WriteCapacityUnits": 15}})`

#### Scenario: AnalysisTable creation
- **WHEN** deploying infrastructure
- **THEN** CDK creates AnalysisTable with article_id PK and 10 WCU Provisioned Capacity
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies table properties
  - **Assertion**: `template.hasResourceProperties("AWS::DynamoDB::Table", {"KeySchema": [{"AttributeName": "article_id", "KeyType": "HASH"}], "ProvisionedThroughput": {"WriteCapacityUnits": 10}})`

### Requirement: SQS Dead Letter Queue
The system SHALL create a DLQ for failed Stream processing.

#### Scenario: DLQ creation
- **WHEN** deploying infrastructure
- **THEN** CDK creates an SQS queue with 14-day message retention
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies SQS queue properties
  - **Assertion**: `template.hasResourceProperties("AWS::SQS::Queue", {"MessageRetentionPeriod": 1209600})`

#### Scenario: DLQ as failure destination
- **WHEN** configuring Analyzer Lambda Event Source Mapping
- **THEN** the system sets DLQ as the On Failure Destination
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies Event Source Mapping destination config
  - **Assertion**: `template.hasResourceProperties("AWS::Lambda::EventSourceMapping", {"DestinationConfig": {"OnFailure": {"Destination": Match.anyValue()}}})`

### Requirement: EventBridge Rules
The system SHALL create daily and weekly EventBridge rules.

#### Scenario: Rules creation
- **WHEN** deploying infrastructure
- **THEN** CDK creates two EventBridge rules targeting Scraper Lambda
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies 2 EventBridge rules exist
  - **Assertion**: `template.resourceCountIs("AWS::Events::Rule", 2)`

#### Scenario: Rule payloads
- **WHEN** configuring rules
- **THEN** daily rule sends {"schedule": "daily"} and weekly rule sends {"schedule": "weekly"}
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies rule input transformers or constants
  - **Assertion**: `template.hasResourceProperties("AWS::Events::Rule", {"Targets": Match.arrayWith([Match.objectLike({"Input": Match.stringLikeRegexp("daily")})])})`

### Requirement: SSM Parameter Store Integration
The system SHALL configure Lambda to read from SSM Parameter Store.

#### Scenario: Prompt template parameter
- **WHEN** deploying Analyzer Lambda
- **THEN** CDK grants read access to /digital-twins-scraper/prompts/analysis
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies IAM policy includes ssm:GetParameter
  - **Assertion**: `template.hasResourceProperties("AWS::IAM::Policy", {"PolicyDocument": {"Statement": Match.arrayWith([Match.objectLike({"Action": Match.arrayWith(["ssm:GetParameter"])})])}})`

#### Scenario: API key parameter
- **WHEN** deploying Analyzer Lambda
- **THEN** CDK grants read access to /digital-twins-scraper/llm-api-key SecureString with KMS decrypt
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies IAM policy includes kms:Decrypt
  - **Assertion**: `template.hasResourceProperties("AWS::IAM::Policy", {"PolicyDocument": {"Statement": Match.arrayWith([Match.objectLike({"Action": Match.arrayWith(["kms:Decrypt"])})])}})`

### Requirement: IAM Least Privilege
The system SHALL configure Lambda execution roles with minimum required permissions.

#### Scenario: Scraper Lambda permissions
- **WHEN** creating Scraper Lambda role
- **THEN** the role includes DynamoDB PutItem (with condition), SSM GetParameter
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies IAM policy statements
  - **Assertion**: `template.hasResourceProperties("AWS::IAM::Policy", {"PolicyDocument": {"Statement": Match.arrayWith([Match.objectLike({"Action": Match.arrayWith(["dynamodb:PutItem"])})])}})`

#### Scenario: Analyzer Lambda permissions
- **WHEN** creating Analyzer Lambda role
- **THEN** the role includes DynamoDB PutItem, SSM GetParameter, KMS Decrypt, SQS SendMessage (DLQ)
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies all required actions in IAM policy
  - **Assertion**: Verify policy includes dynamodb:PutItem, ssm:GetParameter, kms:Decrypt, sqs:SendMessage

### Requirement: CloudWatch Log Groups
The system SHALL create CloudWatch Log Groups with 7-day retention.

#### Scenario: Log group creation
- **WHEN** deploying Lambda functions
- **THEN** CDK creates /aws/lambda/digital-twins-scraper and /aws/lambda/digital-twins-analyzer with 7-day retention
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies log group retention days
  - **Assertion**: `template.hasResourceProperties("AWS::Logs::LogGroup", {"RetentionInDays": 7})`

### Requirement: CloudWatch Alarms
The system SHALL create alarms for Lambda errors, DLQ messages, and Lambda duration.

#### Scenario: Error alarm
- **WHEN** Lambda errors exceed 3 in 5 minutes
- **THEN** CloudWatch Alarm triggers SNS email notification
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies alarm threshold and period
  - **Assertion**: `template.hasResourceProperties("AWS::CloudWatch::Alarm", {"MetricName": "Errors", "Threshold": 3, "Period": 300})`

#### Scenario: DLQ alarm
- **WHEN** DLQ message count exceeds 0
- **THEN** CloudWatch Alarm triggers SNS email notification
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies DLQ alarm configuration
  - **Assertion**: `template.hasResourceProperties("AWS::CloudWatch::Alarm", {"MetricName": "ApproximateNumberOfMessagesVisible", "Threshold": 0, "ComparisonOperator": "GreaterThanThreshold"})`

#### Scenario: Duration alarm
- **WHEN** Lambda p99 duration exceeds 4 minutes
- **THEN** CloudWatch Alarm triggers SNS email notification
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies duration alarm with p99 statistic
  - **Assertion**: `template.hasResourceProperties("AWS::CloudWatch::Alarm", {"MetricName": "Duration", "Threshold": 240000, "ExtendedStatistic": "p99"})`
