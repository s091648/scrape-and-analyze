## ADDED Requirements

### Requirement: GitHub Actions OIDC Authentication
The system SHALL use OIDC federation for AWS authentication instead of long-lived credentials.

#### Scenario: OIDC token exchange
- **WHEN** GitHub Actions workflow runs
- **THEN** the workflow exchanges GitHub OIDC token for AWS temporary credentials
- **Acceptance Criteria**:
  - **Tool**: GitHub Actions workflow validation + YAML lint
  - **Validation**: Verify workflow uses aws-actions/configure-aws-credentials with role-to-assume
  - **Assertion**: Workflow YAML contains `role-to-assume:` and does not contain `aws-access-key-id:`

#### Scenario: No static credentials
- **WHEN** configuring GitHub repository
- **THEN** no AWS access keys are stored in GitHub secrets
- **Acceptance Criteria**:
  - **Tool**: GitHub API / Manual review
  - **Validation**: Check repository secrets do not include AWS_ACCESS_KEY_ID
  - **Assertion**: `gh secret list` does not show AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY

### Requirement: Trust Policy Restriction
The system SHALL restrict AWS IAM role trust policy to specific GitHub repository and branch.

#### Scenario: Main branch only
- **WHEN** configuring trust policy
- **THEN** only main branch of the specific repository can assume the deployment role
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion or IAM policy review
  - **Validation**: Trust policy condition includes repo:owner/repo:ref:refs/heads/main
  - **Assertion**: Trust policy StringEquals condition contains `"token.actions.githubusercontent.com:sub": "repo:*/scrape-analyzer:ref:refs/heads/main"`

#### Scenario: Unauthorized branch attempt
- **WHEN** a non-main branch attempts to assume the role
- **THEN** AWS denies the assume role request
- **Acceptance Criteria**:
  - **Tool**: E2E test or manual verification
  - **Validation**: Feature branch workflow fails at configure-aws-credentials step
  - **Assertion**: Workflow log shows "Error: Could not assume role"

### Requirement: Minimum IAM Permissions
The system SHALL configure deployment role with least privilege permissions.

#### Scenario: CloudFormation permissions
- **WHEN** deploying CDK stacks
- **THEN** the role has cloudformation:* permissions
- **Acceptance Criteria**:
  - **Tool**: IAM policy review or AWS CDK assertion
  - **Validation**: Policy document includes cloudformation:* action
  - **Assertion**: `"cloudformation:*"` in policy actions

#### Scenario: Lambda permissions
- **WHEN** deploying Lambda functions
- **THEN** the role has lambda:* permissions
- **Acceptance Criteria**:
  - **Tool**: IAM policy review
  - **Validation**: Policy document includes lambda:* action
  - **Assertion**: `"lambda:*"` in policy actions

#### Scenario: DynamoDB permissions
- **WHEN** creating DynamoDB tables
- **THEN** the role has dynamodb:CreateTable, UpdateTable, DeleteTable, DescribeTable, DescribeStream, GetRecords, GetShardIterator, ListStreams
- **Acceptance Criteria**:
  - **Tool**: IAM policy review
  - **Validation**: Policy includes all required DynamoDB actions
  - **Assertion**: All listed actions present in policy document

#### Scenario: ECR permissions
- **WHEN** pushing Docker images
- **THEN** the role has ecr:GetAuthorizationToken (global) and specific repository permissions
- **Acceptance Criteria**:
  - **Tool**: IAM policy review
  - **Validation**: Policy includes ECR actions with appropriate resource constraints
  - **Assertion**: `ecr:GetAuthorizationToken` with `"Resource": "*"` and other ECR actions with specific repo ARN

#### Scenario: SQS permissions
- **WHEN** creating SQS queues
- **THEN** the role has limited SQS permissions scoped to project resources
- **Acceptance Criteria**:
  - **Tool**: IAM policy review
  - **Validation**: SQS actions have Resource constraint to project queues
  - **Assertion**: `"Resource": "arn:aws:sqs:*:*:digital-twins-*"`

#### Scenario: EventBridge permissions
- **WHEN** creating EventBridge rules
- **THEN** the role has limited Events permissions scoped to project resources
- **Acceptance Criteria**:
  - **Tool**: IAM policy review
  - **Validation**: Events actions have Resource constraint
  - **Assertion**: `"Resource": "arn:aws:events:*:*:rule/digital-twins-*"`

#### Scenario: SSM permissions
- **WHEN** managing parameters
- **THEN** the role has ssm:GetParameter, PutParameter permissions
- **Acceptance Criteria**:
  - **Tool**: IAM policy review
  - **Validation**: Policy includes SSM parameter actions
  - **Assertion**: `["ssm:GetParameter", "ssm:PutParameter"]` in policy actions

#### Scenario: KMS permissions
- **WHEN** reading SecureString parameters
- **THEN** the role has kms:Decrypt permission for AWS managed key
- **Acceptance Criteria**:
  - **Tool**: IAM policy review
  - **Validation**: Policy includes kms:Decrypt
  - **Assertion**: `"kms:Decrypt"` in policy actions

### Requirement: Unit Test Execution
The system SHALL run unit tests with coverage requirements in CI.

#### Scenario: Unit test stage
- **WHEN** PR is created or push to main
- **THEN** GitHub Actions runs pytest tests/unit --cov=lambda --cov-fail-under=80
- **Acceptance Criteria**:
  - **Tool**: GitHub Actions workflow validation
  - **Validation**: Workflow YAML contains pytest command with coverage flags
  - **Assertion**: Workflow contains `pytest tests/unit --cov=lambda --cov-fail-under=80`

#### Scenario: Coverage failure
- **WHEN** code coverage is below 80%
- **THEN** the CI pipeline fails
- **Acceptance Criteria**:
  - **Tool**: pytest-cov + GitHub Actions
  - **Validation**: Workflow with 70% coverage code fails at test step
  - **Assertion**: Workflow exits with non-zero code when coverage < 80%

### Requirement: Integration Test Execution
The system SHALL run integration tests using LocalStack.

#### Scenario: Integration test stage
- **WHEN** unit tests pass
- **THEN** GitHub Actions runs pytest tests/integration with LocalStack
- **Acceptance Criteria**:
  - **Tool**: GitHub Actions workflow validation
  - **Validation**: Workflow starts LocalStack service before integration tests
  - **Assertion**: Workflow contains `services: localstack:` or `docker run localstack`

#### Scenario: LocalStack services
- **WHEN** running integration tests
- **THEN** LocalStack provides DynamoDB and SQS emulation
- **Acceptance Criteria**:
  - **Tool**: LocalStack configuration + pytest
  - **Validation**: Integration tests successfully connect to LocalStack DynamoDB and SQS
  - **Assertion**: Tests create tables and queues in LocalStack without AWS credentials

### Requirement: E2E Test on Main Branch
The system SHALL run E2E tests only when merging to main branch.

#### Scenario: E2E trigger
- **WHEN** PR is merged to main
- **THEN** GitHub Actions runs E2E tests against staging environment
- **Acceptance Criteria**:
  - **Tool**: GitHub Actions workflow validation
  - **Validation**: E2E job has condition `if: github.ref == 'refs/heads/main'`
  - **Assertion**: Workflow YAML E2E job contains branch condition

#### Scenario: Non-main branches
- **WHEN** running CI on feature branches
- **THEN** E2E tests are skipped
- **Acceptance Criteria**:
  - **Tool**: GitHub Actions workflow run history
  - **Validation**: Feature branch workflow shows E2E job as skipped
  - **Assertion**: E2E job status is "skipped" for feature branch runs

### Requirement: CDK Deployment
The system SHALL deploy CDK stacks after all tests pass.

#### Scenario: Successful deployment
- **WHEN** all tests pass on main branch
- **THEN** GitHub Actions runs cdk deploy
- **Acceptance Criteria**:
  - **Tool**: GitHub Actions workflow validation
  - **Validation**: Deploy job depends on test jobs and runs cdk deploy
  - **Assertion**: Workflow contains `needs: [unit-test, integration-test]` and `cdk deploy`

#### Scenario: Deployment failure
- **WHEN** CDK deployment fails
- **THEN** GitHub Actions reports failure and the workflow stops
- **Acceptance Criteria**:
  - **Tool**: GitHub Actions + manual test
  - **Validation**: Intentionally broken CDK code shows failed deploy step
  - **Assertion**: Workflow status is "failure" and subsequent steps are skipped
