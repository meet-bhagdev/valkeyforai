## Pattern 1: Retry-After Headers  
  
Always tell clients **when** to retry:

```python
import os
from dotenv import load_dotenv

load_dotenv()

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
```

## Pattern 2: Graceful Degradation

Don't hard-fail - degrade gracefully through model tiers, cache, then queue:

```python
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
```

## Pattern 3: Circuit Breaker

If Valkey goes down, fail-open (allow requests) rather than blocking everything:

```python
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
```

## Pattern 4: Request Queuing with Streams

```python
def enqueue_request(user_id, prompt, model="gpt-4"):
    client.xadd("llm:queue", {
        "user_id": user_id,
        "prompt": prompt,
        "model": model,
        "queued_at": str(time.time()),
    }, maxlen=10000)
```

## Production Checklist

  * **Retry-After headers** on every 429 response
  * **Circuit breaker** for Valkey connection failures
  * **Fail-open policy** - never block users because of infra issues
  * **Graceful degradation** - cheaper models before hard rejection
  * **Request queuing** - don't lose requests, queue them
  * **Observability** - log every allow/deny decision
  * **Dynamic config** - update limits without redeploying
  * **Connection pooling** - reuse Valkey connections
  * **Lua scripts** - atomic check-and-increment for correctness

## Valkey Configuration

```python
# valkey.conf optimizations for rate limiting
maxmemory 256mb
maxmemory-policy allkeys-lru
hz 100
tcp-keepalive 300
timeout 0
```

**Full Series Complete!** You now have everything you need to implement production-grade rate limiting for AI workloads. All code is open source - [clone the repo](<https://github.com/meet-bhagdev/valkeyforai/tree/main>) and start shipping.