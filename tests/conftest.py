"""
Shared pytest fixtures.
Resets the rate limiter storage between tests so API tests don't bleed into each other.
"""
import pytest
from main import app, limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear in-memory rate limit counters before every test."""
    limiter.reset()
    yield
