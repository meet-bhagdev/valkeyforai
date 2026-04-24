"""Integration tests for Rate Limiting - Production Patterns.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_06_production(client):
    """Run all code blocks from: Production Patterns."""

    # --- Block 1 ---
    from fastapi import FastAPI, Response, HTTPException

    app = FastAPI()

    @app.post("/api/chat")
    async def chat(prompt: str, response: Response):
        result = limiter.check(tokens=count_tokens(prompt))

        response.headers["X-RateLimit-Limit"] = str(result.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)

        if not result.allowed:
            response.headers["Retry-After"] = str(int(result.retry_after_seconds))
            raise HTTPException(status_code=429, detail={
                "error": "rate_limit_exceeded",
                "retry_after_seconds": result.retry_after_seconds,
            })
        return await call_llm(prompt)

    # --- Block 2 ---
    async def smart_llm_call(prompt, user_id):
        # Tier 1: Preferred model
        result = limiter.check(user_id, model="gpt-4")
        if result.allowed:
            return await call_llm(prompt, model="gpt-4")

        # Tier 2: Cheaper model
        result = limiter.check(user_id, model="gpt-3.5-turbo")
        if result.allowed:
            return await call_llm(prompt, model="gpt-3.5-turbo")

        # Tier 3: Semantic cache
        cached = await semantic_cache_lookup(prompt)
        if cached:
            return {"response": cached, "source": "cache"}

        # Tier 4: Queue for later
        await enqueue_request(user_id, prompt)
        return {"response": "Queued for processing", "source": "queued"}

    # --- Block 3 ---
    class RateLimiterWithCircuitBreaker:
        def __init__(self):
            self.failure_count = 0
            self.failure_threshold = 3
            self.circuit_open_until = 0

        def check(self, tokens):
            if time.time() < self.circuit_open_until:
                return {"allowed": True, "source": "circuit_breaker"}
            try:
                result = self._do_check(tokens)
                self.failure_count = 0
                return result
            except Exception:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self.circuit_open_until = time.time() + 30
                return {"allowed": True, "source": "fallback"}

