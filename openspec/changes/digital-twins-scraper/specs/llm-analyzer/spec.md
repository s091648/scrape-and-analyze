## ADDED Requirements

### Requirement: Article Content Analysis
The system SHALL analyze article content using LLM to extract structured insights.

#### Scenario: Successful analysis
- **WHEN** article content is submitted for analysis
- **THEN** the system returns: tags, pain points, insights, innovations

#### Scenario: Empty content
- **WHEN** article content is empty or whitespace only
- **THEN** the system skips analysis and records a failure

#### Scenario: Content too long
- **WHEN** article content exceeds LLM context limit
- **THEN** the system truncates content to fit within limits

### Requirement: LLM Provider Abstraction
The system SHALL support multiple LLM providers through an abstraction layer.

#### Scenario: Use Claude provider
- **WHEN** LLM_PROVIDER is set to "claude"
- **THEN** the system uses Anthropic's Claude API for analysis

#### Scenario: Provider selection via environment
- **WHEN** the system initializes
- **THEN** the system reads LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY from environment variables

#### Scenario: Invalid provider
- **WHEN** LLM_PROVIDER is set to an unsupported value
- **THEN** the system raises a configuration error at startup

### Requirement: Analysis Output Format
The system SHALL return analysis results in a structured JSON format.

#### Scenario: Valid JSON output
- **WHEN** LLM returns analysis
- **THEN** the system parses and validates JSON with: tags (array), pain_points (string), insights (string), innovations (string)

#### Scenario: Invalid JSON response
- **WHEN** LLM returns malformed JSON
- **THEN** the system logs the error and retries with adjusted prompt

#### Scenario: Missing required fields
- **WHEN** LLM response is missing required fields
- **THEN** the system logs the error and retries

### Requirement: Token Usage Tracking
The system SHALL track LLM token usage for cost monitoring.

#### Scenario: Track input tokens
- **WHEN** calling LLM API
- **THEN** the system records the input token count from API response

#### Scenario: Track output tokens
- **WHEN** receiving LLM response
- **THEN** the system records the output token count from API response

#### Scenario: Log token metrics
- **WHEN** analysis completes
- **THEN** the system logs input_tokens, output_tokens, and model_used

### Requirement: Prompt Template Management
The system SHALL use configurable prompt templates for analysis.

#### Scenario: Load prompt template
- **WHEN** initializing analyzer
- **THEN** the system loads prompt template from src/prompts/analysis.txt

#### Scenario: Prompt structure
- **WHEN** constructing analysis request
- **THEN** the system uses XML-style delimiters to separate system instructions from article content

#### Scenario: Update prompt without redeploy
- **WHEN** prompt template file is modified
- **THEN** the system uses updated template on next execution

### Requirement: Prompt Injection Protection
The system SHALL protect against prompt injection attacks.

#### Scenario: Content sanitization before LLM
- **WHEN** preparing content for LLM analysis
- **THEN** the system escapes or removes potentially malicious prompt patterns

#### Scenario: Output validation
- **WHEN** receiving LLM response
- **THEN** the system validates response matches expected schema

### Requirement: LLM API Retry Logic
The system SHALL implement retry logic for LLM API failures.

#### Scenario: Transient API error
- **WHEN** LLM API returns 5xx error
- **THEN** the system retries up to 3 times with exponential backoff

#### Scenario: Rate limit error
- **WHEN** LLM API returns 429 rate limit error
- **THEN** the system waits with exponential backoff (min 4s, max 60s) and retries

#### Scenario: Retry exhausted
- **WHEN** all retries fail
- **THEN** the system records failure and continues with next article
