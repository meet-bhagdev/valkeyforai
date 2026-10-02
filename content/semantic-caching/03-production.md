## Pattern 1: Similarity Threshold Tuning

The threshold controls the trade-off between hit rate and answer quality:

| Threshold (COSINE) | Hit Rate | Quality Risk | Best For |
|---|---|---|---|
| `0.05` (very strict) | Low (~20%) | Very low | Medical, legal, financial |
| `0.15` (balanced) | Medium (~50%) | Low | General chatbots |
| `0.30` (relaxed) | High (~70%) | Medium | FAQ bots, support |
| `0.50` (very relaxed) | Very high (~85%) | High - stale answers | Not recommended |

```python
# Test different thresholds to find the right balance
def evaluate_threshold(test_pairs: list, threshold: float):
    """Evaluate cache quality at a given threshold."""
    hits = 0
    false_positives = 0

    for query, expected_similar in test_pairs:
        result = semantic_cache_lookup(query)
        if result["hit"] and result["score"] < threshold:
            hits += 1
            if not expected_similar:
                false_positives += 1

    hit_rate = hits / len(test_pairs)
    fp_rate = false_positives / max(1, hits)
    print(f"Threshold {threshold}: hit_rate={hit_rate:.1%}, false_positive_rate={fp_rate:.1%}")
```

## Pattern 2: Cache Hit Rate Monitoring

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey

client = valkey.Valkey(host="localhost", port=6379)

def record_cache_event(event_type: str):
    """Track cache hits and misses using atomic counters."""
    client.incr(f"cache:metrics:{event_type}")

    # Also track hourly for time-series analysis
    from datetime import datetime
    hour_key = datetime.now().strftime("%Y%m%d%H")
    counter_key = f"cache:metrics:{event_type}:{hour_key}"
    client.incr(counter_key)
    client.expire(counter_key, 86400 * 7)  # Keep 7 days

def get_cache_stats() -> dict:
    """Get current cache performance metrics."""
    hits = int(client.get("cache:metrics:hit") or 0)
    misses = int(client.get("cache:metrics:miss") or 0)
    total = hits + misses
    hit_rate = hits / total if total > 0 else 0

    # Estimate cost savings (GPT-4: ~$0.03/1K tokens, avg 500 tokens/request)
    avg_cost_per_call = 0.015
    savings = hits * avg_cost_per_call

    return {
        "total_requests": total,
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hit_rate, 3),
        "estimated_savings_usd": round(savings, 2),
    }

# Usage in ask_with_cache:
# if cache_hit: record_cache_event("hit")
# else: record_cache_event("miss")
```

## Pattern 3: TTL Strategies

```python
# Strategy 1: Fixed TTL - simple, predictable
client.expire(cache_key, 3600)  # 1 hour

# Strategy 2: Category-based TTL
TTL_MAP = {
    "factual": 86400,      # 24h - facts don't change fast
    "opinion": 3600,       # 1h - opinions evolve
    "real-time": 300,      # 5 min - stock prices, weather
    "conversation": 1800,  # 30 min - chat context
}

# Strategy 3: Sliding TTL - reset on each hit
def cache_hit_with_refresh(cache_key: str, ttl: int = 3600):
    """On cache hit, refresh the TTL to keep popular entries alive."""
    response = client.hget(cache_key, "response")
    client.expire(cache_key, ttl)  # Reset TTL
    return response
```

## Pattern 4: Memory Management

```python
# Set maxmemory policy for cache eviction
# In valkey.conf or via CONFIG SET:
# maxmemory 1gb
# maxmemory-policy allkeys-lru
#
# LRU = Least Recently Used - evicts least-accessed cache entries first
# This is ideal for semantic caching where popular queries should stay

# Check memory usage
info = client.info("memory")
used_mb = info["used_memory"] / (1024 * 1024)
print(f"Memory: {used_mb:.1f} MB")

# Estimate cache capacity
# Each entry: ~6KB (1536 dims * 4 bytes + prompt + response text)
# 1 GB ≈ ~170,000 cached entries
```

## Pattern 5: Cache Invalidation

```python
# Invalidate specific cached entries
def invalidate_by_topic(topic_keyword: str):
    """Remove cached entries matching a topic (e.g., after a data update)."""
    results = client.execute_command(
        "FT.SEARCH", "cache_idx",
        f"@prompt:{topic_keyword}",
        "NOCONTENT",  # Only return keys, not fields
    )

    if results[0] > 0:
        keys = results[1:]
        for key in keys:
            client.delete(key)
        print(f"Invalidated {len(keys)} cached entries for '{topic_keyword}'")

# Example: product info changed, invalidate related cache
invalidate_by_topic("pricing")
```

## Production Checklist

| Area | Recommendation |
|------|---------------|
| Threshold | Start at 0.15 (COSINE), tune with A/B testing |
| TTL | 1h for general, 24h for facts, 5min for real-time |
| Monitoring | Track hit rate, latency, cost savings hourly |
| Memory | Set `maxmemory-policy allkeys-lru` |
| Invalidation | Use TEXT search to find and delete stale entries |
| Isolation | TAG filters for multi-tenant deployments |
| Embeddings | Use `text-embedding-3-small` (fast, cheap, 1536 dims) |
| Index | HNSW with COSINE for OpenAI/Bedrock embeddings |

> **Reference:** This pattern is described in the official AWS documentation for [ElastiCache semantic caching use cases](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/elasticache-use-cases.html), and was featured in the AWS re:Invent session on semantic caching for multi-turn agents with ElastiCache.
