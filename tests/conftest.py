import pytest
import os

# Set test environment
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_db')
