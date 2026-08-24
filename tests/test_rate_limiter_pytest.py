"""
Pytest test suite for RateLimiter (Task 14)

Run with: pytest tests/test_rate_limiter_pytest.py -v
"""

import time

import pytest

from src.data_ingestion.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_rejects_non_positive_calls_per_minute(self):
        with pytest.raises(ValueError):
            RateLimiter(0)
        with pytest.raises(ValueError):
            RateLimiter(-5)

    def test_first_call_does_not_wait(self):
        limiter = RateLimiter(calls_per_minute=60)
        slept = limiter.wait_if_needed()
        assert slept == 0.0

    def test_second_call_waits_approximately_min_interval(self):
        limiter = RateLimiter(calls_per_minute=600)  # 0.1s interval
        limiter.wait_if_needed()
        start = time.monotonic()
        limiter.wait_if_needed()
        elapsed = time.monotonic() - start
        assert 0.08 <= elapsed <= 0.3  # allow scheduling slack

    def test_call_after_natural_delay_does_not_over_wait(self):
        limiter = RateLimiter(calls_per_minute=600)  # 0.1s interval
        limiter.wait_if_needed()
        time.sleep(0.15)  # already longer than the min interval
        start = time.monotonic()
        limiter.wait_if_needed()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05  # should not sleep again

    def test_reset_clears_internal_clock(self):
        limiter = RateLimiter(calls_per_minute=600)
        limiter.wait_if_needed()
        limiter.reset()
        slept = limiter.wait_if_needed()
        assert slept == 0.0  # behaves like a first call again


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
