## ADDED Requirements

### Requirement: LLM Provider Abstraction
The system SHALL implement an abstract LLMProvider interface to support multiple LLM providers.

#### Scenario: Claude provider implementation
- **WHEN** LLM_PROVIDER environment variable is set to "claude"
- **THEN** the system uses ClaudeProvider with the configured model
- **Acceptance Criteria**:
  - **Tool**: pytest + unittest.mock + monkeypatch
  - **Validation**: Unit test sets LLM_PROVIDER=claude, verifies ClaudeProvider is instantiated
  - **Assertion**: `assert isinstance(get_provider(), ClaudeProvider)`

#### Scenario: Provider switching
- **WHEN** switching from Claude to another provider
- **THEN** the system requires only configuration changes, no code modification
- **Acceptance Criteria**:
  - **Tool**: pytest + ABC inspection
  - **Validation**: Unit test verifies LLMProvider is abstract class with analyze() method
  - **Assertion**: `assert inspect.isabstract(LLMProvider)` and `assert "analyze" in LLMProvider.__abstractmethods__`

### Requirement: Content Analysis
The system SHALL analyze article content to extract tags, pain_points, insights, and innovations.

#### Scenario: Successful analysis
- **WHEN** LLM receives sanitized article content
- **THEN** the system returns a JSON object with tags (array), pain_points (string), insights (string), and innovations (string)
- **Acceptance Criteria**:
  - **Tool**: pytest + responses (mock Anthropic API)
  - **Validation**: Unit test with mocked LLM response returns AnalysisResult with all fields
  - **Assertion**: `assert isinstance(result.tags, list)` and `assert result.pain_points` and `assert result.insights`

#### Scenario: Analysis output validation
- **WHEN** LLM returns a response
- **THEN** the system validates the response against the expected JSON Schema
- **Acceptance Criteria**:
  - **Tool**: pytest + jsonschema
  - **Validation**: Unit test validates LLM output against defined schema
  - **Assertion**: `jsonschema.validate(result, ANALYSIS_SCHEMA)` does not raise ValidationError

### Requirement: Prompt Injection Prevention
The system SHALL implement safeguards against prompt injection attacks.

#### Scenario: Special character filtering
- **WHEN** article content contains special characters that could interfere with prompts
- **THEN** the system filters these characters before sending to LLM
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test with content containing `</system>` or `<|endoftext|>` removes these sequences
  - **Assertion**: `assert "</system>" not in sanitized_content` and `assert "<|" not in sanitized_content`

#### Scenario: Structured prompt with delimiters
- **WHEN** constructing the LLM prompt
- **THEN** the system uses clear delimiters (system/article tags) to separate instructions from content
- **Acceptance Criteria**:
  - **Tool**: pytest + string inspection
  - **Validation**: Unit test verifies prompt contains <system>, </system>, <article>, </article> tags
  - **Assertion**: `assert "<system>" in prompt` and `assert "<article>" in prompt`

### Requirement: API Key Security
The system SHALL retrieve LLM API keys from SSM Parameter Store SecureString.

#### Scenario: API key retrieval
- **WHEN** Analyzer Lambda starts
- **THEN** the system retrieves the API key from SSM Parameter Store with decryption
- **Acceptance Criteria**:
  - **Tool**: pytest + moto (mock SSM)
  - **Validation**: Integration test verifies get_parameter called with WithDecryption=True
  - **Assertion**: `mock_ssm.get_parameter.assert_called_with(Name="/digital-twins-scraper/llm-api-key", WithDecryption=True)`

#### Scenario: API key not in environment
- **WHEN** checking Lambda environment variables
- **THEN** only the parameter name is stored, not the actual API key
- **Acceptance Criteria**:
  - **Tool**: AWS CDK assertion
  - **Validation**: CDK test verifies Lambda environment has LLM_API_KEY_PARAM_NAME, not the actual key
  - **Assertion**: `template.hasResourceProperties("AWS::Lambda::Function", {"Environment": {"Variables": {"LLM_API_KEY_PARAM_NAME": Match.anyValue()}}})`

### Requirement: Prompt Template Externalization
The system SHALL store prompt templates in SSM Parameter Store for runtime updates.

#### Scenario: Prompt template retrieval
- **WHEN** preparing to analyze an article
- **THEN** the system fetches the prompt template from SSM Parameter Store
- **Acceptance Criteria**:
  - **Tool**: pytest + moto
  - **Validation**: Integration test verifies SSM get_parameter called for prompt path
  - **Assertion**: `assert "/digital-twins-scraper/prompts/analysis" in ssm_calls`

#### Scenario: Prompt update without deployment
- **WHEN** updating the prompt template in SSM
- **THEN** the change takes effect without redeploying Lambda
- **Acceptance Criteria**:
  - **Tool**: E2E test (manual or automated)
  - **Validation**: Update SSM parameter, invoke Lambda, verify new prompt used
  - **Assertion**: Lambda response reflects new prompt behavior (documented in E2E test plan)

### Requirement: Token and Latency Monitoring
The system SHALL log LLM API metrics for cost and performance analysis.

#### Scenario: Metrics logging
- **WHEN** completing an LLM API call
- **THEN** the system logs llm_latency_ms, input_token_count, and output_token_count
- **Acceptance Criteria**:
  - **Tool**: pytest + caplog (logging capture)
  - **Validation**: Unit test captures log output, verifies JSON contains metric fields
  - **Assertion**: `assert "llm_latency_ms" in log_json` and `assert "input_token_count" in log_json`

### Requirement: LLM Response Error Handling
The system SHALL handle malformed or empty LLM responses gracefully.

#### Scenario: Malformed JSON response
- **WHEN** LLM returns invalid JSON
- **THEN** the system marks the analysis as failed and logs the raw response
- **Acceptance Criteria**:
  - **Tool**: pytest + responses + caplog
  - **Validation**: Unit test with "not valid json" response logs error, returns None/raises AnalysisError
  - **Assertion**: `assert result is None` or `pytest.raises(AnalysisError)` and `assert "malformed" in caplog.text.lower()`

#### Scenario: Empty response
- **WHEN** LLM returns an empty response
- **THEN** the system marks the analysis as failed and does not store results
- **Acceptance Criteria**:
  - **Tool**: pytest + responses
  - **Validation**: Unit test with empty string response returns failure, no DB write attempted
  - **Assertion**: `assert result is None` and `mock_db.put_item.assert_not_called()`

### Requirement: Content Token Limit
The system SHALL truncate content to 50,000 characters before sending to LLM.

#### Scenario: Content exceeds LLM limit
- **WHEN** sanitized content exceeds 50,000 characters
- **THEN** the system truncates before sending to LLM to fit context window
- **Acceptance Criteria**:
  - **Tool**: pytest
  - **Validation**: Unit test with 100,000 char content verifies LLM receives max 50,000 chars
  - **Assertion**: `assert len(content_sent_to_llm) <= 50000`
