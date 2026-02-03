"""
tests/conftest.py
"""
import pytest
import os
import sys

# Add src to path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("S3_BUCKET", "test_bucket")
