## The Problem

LLM API calls are expensive ($0.003–$0.10+ per call) and slow (2–10 seconds). Users often send identical or near-identical prompts:

  * Multiple users asking the same FAQ
  * Retry logic re-sending the same prompt
  * Agents re-invoking the same tool with the same input

Exact-match caching eliminates redundant calls. (For meaning-based matching, see [Guide 03](<03-semantic-search.html>).)

**Upstream Contribution:** The `ValkeyCache` integration was contributed to `langchain-ai/langchain-aws` in [PR #717](<https://github.com/langchain-ai/langchain-aws/pull/717>) by the Valkey team.

## Step 1: Initialize ValkeyCache

```python
import os
from dotenv import load_dotenv

load_dotenv()

from langgraph_checkpoint_aws import ValkeyCache
from valkey import Valkey

# Create Valkey client
valkey_client = Valkey.from_url(
    "valkey://localhost:6379",
    decode_responses=False,
)

# Initialize cache with 1-hour TTL
cache = ValkeyCache(
    client=valkey_client,
    prefix="llm_cache:",
    ttl=3600,
)
```

## Step 2: Cache Key Generation

Generate deterministic keys from prompt + model + temperature so different model configs don't collide:

```python
import hashlib

def cache_key(prompt: str, model: str = "claude-sonnet", temp: float = 0.7) -> tuple:
    content = f"{model}|temp={temp}|{prompt.strip()}"
    key = hashlib.sha256(content.encode()).hexdigest()[:16]
    return (("llm_responses",), key)
```

## Step 3: Cached Inference Function

```python
import time
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage

model = ChatBedrockConverse(
    model="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-west-2",
)

async def cached_llm_call(prompt: str) -> dict:
    key = cache_key(prompt)

    # 1. Check cache
    start = time.time()
    cached = await cache.aget([key])
    cache_time = time.time() - start

    if key in cached:
        return {
            "response": cached[key]["response"],
            "cached": True,
            "latency_ms": cache_time * 1000,
        }

    # 2. Cache miss - call LLM
    start = time.time()
    response = await model.ainvoke([HumanMessage(content=prompt)])
    llm_time = time.time() - start

    # 3. Store in cache
    await cache.aset({key: ({"response": response.content}, 3600)})

    return {
        "response": response.content,
        "cached": False,
        "latency_ms": llm_time * 1000,
    }
```

## Step 4: Benchmark - The Dramatic Difference

```python
import asyncio

async def benchmark():
    prompt = "What is Amazon ElastiCache for Valkey?"

    # First call - cache miss
    r1 = await cached_llm_call(prompt)
    print(f"❌ Cache MISS: {r1['latency_ms']:.0f}ms")

    # Second call - cache hit
    r2 = await cached_llm_call(prompt)
    print(f"✅ Cache HIT:  {r2['latency_ms']:.1f}ms")

    speedup = r1["latency_ms"] / r2["latency_ms"]
    print(f"🚀 Speedup:   {speedup:.0f}x faster")

asyncio.run(benchmark())

# Output:
# ❌ Cache MISS: 4200ms
# ✅ Cache HIT:  1.2ms
# 🚀 Speedup:   3500x faster
```

## Step 5: TTL Management

```python
# Default TTL (set at cache creation)
cache = ValkeyCache(client=valkey_client, ttl=3600)  # 1 hour

# Custom TTL per entry
await cache.aset({key: (data, 300)})  # 5 minutes for volatile data

# Clear all cached entries
await cache.aclear()
```

**Valkey Commands Fired:**

```python
# Cache lookup
GET llm_cache:a1b2c3d4e5f6g7h8

# Cache store
SET llm_cache:a1b2c3d4e5f6g7h8 '{"response":"..."}' EX 3600

# Cache clear
SCAN 0 MATCH llm_cache:* COUNT 100
DEL llm_cache:a1b2c3d4e5f6g7h8 ...
```

## Next Steps

Exact-match caching is powerful but misses paraphrased queries. Next, we'll add semantic search to match by meaning.

[Next: 03 Semantic Search with ValkeyStore →](<03-semantic-search.html>)