"""
Rate Limiter

A small, shared, reusable component that paces outgoing API calls to stay
within a provider's requests-per-minute limit. Wrapped around each
ingester's HTTP calls by IngestionEngine (Task 14), configured per-provider
via config/settings.json rather than hardcoded per-ingester.

Design note: this uses a simple fixed-window sleep strategy (sufficient at
the call volumes this project operates at - tens to low hundreds of calls
per cycle). It is not a token-bucket implementation; if burst tolerance or
distributed rate limiting is ever needed, that would replace this class's
internals without changing its public interface (__init__, wait_if_needed).
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """Paces calls to stay within a configured calls-per-minute budget."""

    def __init__(self, calls_per_minute: int):
        """
        Args:
            calls_per_minute: Maximum calls allowed per 60-second window.
                              Must be positive.

        Raises:
            ValueError: If calls_per_minute is not positive
        """
        if calls_per_minute <= 0:
            raise ValueError(f"calls_per_minute must be positive, got {calls_per_minute}")

        self.calls_per_minute = calls_per_minute
        self._min_interval_seconds = 60.0 / calls_per_minute
        self._last_call_time: Optional[float] = None

    def wait_if_needed(self) -> float:
        """
        Block (if necessary) until it is safe to make another call without
        exceeding the configured rate.

        Returns:
            Number of seconds actually slept (0.0 if no wait was needed)
        """
        if self._last_call_time is None:
            self._last_call_time = time.monotonic()
            return 0.0

        elapsed = time.monotonic() - self._last_call_time
        remaining = self._min_interval_seconds - elapsed

        slept = 0.0
        if remaining > 0:
            logger.debug("Rate limiter: sleeping %.2fs to respect %d calls/min",
                         remaining, self.calls_per_minute)
            time.sleep(remaining)
            slept = remaining

        self._last_call_time = time.monotonic()
        return slept

    def reset(self) -> None:
        """Reset the limiter's internal clock (mainly useful for tests)."""
        self._last_call_time = None


if __name__ == "__main__":
    print("=" * 60)
    print("Rate Limiter Test")
    print("=" * 60)
    print()

    limiter = RateLimiter(calls_per_minute=120)  # 1 call every 0.5s
    print(f"Configured for {limiter.calls_per_minute} calls/min "
          f"(min interval: {limiter._min_interval_seconds:.2f}s)")
    print()

    for i in range(4):
        start = time.monotonic()
        slept = limiter.wait_if_needed()
        elapsed = time.monotonic() - start
        print(f"Call {i + 1}: slept {slept:.2f}s (wait_if_needed took {elapsed:.2f}s)")

    print()
    print("=" * 60)
    print("First call should have 0s wait; subsequent calls should pace to ~0.5s")
    print("=" * 60)
