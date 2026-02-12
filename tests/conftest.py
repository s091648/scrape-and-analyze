import pytest
import os

# Set test environment
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_db')
os.environ.setdefault('LLM_API_KEY', 'test-key')
os.environ.setdefault('LLM_PROVIDER', 'claude')
os.environ.setdefault('LLM_MODEL', 'claude-sonnet-4-20250514')
