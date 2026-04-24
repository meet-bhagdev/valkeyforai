"""Integration tests for LangChain - LLM Caching.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_02_llm_caching(client):
    """Run all code blocks from: LLM Caching."""

    # --- Block 1 ---
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

    # --- Block 2 ---
    import hashlib

    def cache_key(prompt: str, model: str = "claude-sonnet", temp: float = 0.7) -> tuple:
        content = f"{model}|temp={temp}|{prompt.strip()}"
        key = hashlib.sha256(content.encode()).hexdigest()[:16]
        return (("llm_responses",), key)

    # --- Block 3 ---
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

    # --- Block 4 ---
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

    # --- Block 5 ---
    # Default TTL (set at cache creation)
    cache = ValkeyCache(client=valkey_client, ttl=3600)  # 1 hour

    # Custom TTL per entry
    await cache.aset({key: (data, 300)})  # 5 minutes for volatile data

    # Clear all cached entries
    await cache.aclear()

