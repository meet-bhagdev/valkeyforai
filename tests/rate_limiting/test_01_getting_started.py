"""Integration tests for Rate Limiting - Getting Started with Rate Limiting.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with Rate Limiting."""

    # --- Block 1 ---
    import time

    client = client

    def check_rate_limit(user_id: str, max_requests: int = 10, window: int = 60) -> dict:
        """Fixed-window rate limiter."""
        window_num = int(time.time() // window)
        key = f"rl:{user_id}:{window_num}"

        pipe = client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, window)
        results = pipe.execute()

        current = results[0]
        allowed = current <= max_requests

        return {
            "allowed": allowed,
            "current": current,
            "limit": max_requests,
            "remaining": max(0, max_requests - current),
        }

    # --- Block 2 ---
    # Send 12 requests - last 2 should be denied
    for i in range(12):
        result = check_rate_limit("user-123", max_requests=10)
        status = "✅" if result["allowed"] else "❌"
        print(f"{status} Request {i+1}: {result['current']}/{result['limit']}")

