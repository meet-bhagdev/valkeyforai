[← All RAG Cookbooks](</cookbooks/rag-pipelines/>)

# Monitoring & Observability

Track cache performance, search latencies, and system health in production.

## Key Metrics to Track

#### Cache Hit Rate

Target: >80% for FAQ, >60% for RAG

#### Search Latency (p99)

Target: <10ms for HNSW

#### Memory Usage

Alert at 80% of maxmemory

#### Connected Clients

Monitor for connection leaks

## Built-in INFO Command

```bash
# Get all stats
INFO

# Specific sections
INFO memory
INFO stats
INFO clients

# Search module stats
FT.INFO idx:docs
```

## Application-Level Metrics

```python
import os
from dotenv import load_dotenv

load_dotenv()

import time
from dataclasses import dataclass, field

@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    hit_latencies: list = field(default_factory=list)
    miss_latencies: list = field(default_factory=list)

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0

    @property
    def avg_hit_latency(self):
        return sum(self.hit_latencies) / len(self.hit_latencies) if self.hit_latencies else 0

metrics = CacheMetrics()

async def cached_query(query):
    start = time.perf_counter()
    result = await cache.lookup(query)
    latency = (time.perf_counter() - start) * 1000

    if result:
        metrics.hits += 1
        metrics.hit_latencies.append(latency)
    else:
        metrics.misses += 1
        metrics.miss_latencies.append(latency)

    return result
```

## Prometheus Integration

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
cache_hits = Counter('rag_cache_hits_total', 'Cache hits')
cache_misses = Counter('rag_cache_misses_total', 'Cache misses')
search_latency = Histogram(
    'rag_search_seconds', 'Search latency',
    buckets=[.001, .005, .01, .05, .1, .5, 1]
)
vector_count = Gauge('rag_vectors_total', 'Total vectors')

# Usage
with search_latency.time():
    results = await vector_store.search(query)

if cache_hit:
    cache_hits.inc()
else:
    cache_misses.inc()
```

## Logging Best Practices

```python
import structlog

log = structlog.get_logger()

async def search_with_logging(query, user_id):
    start = time.perf_counter()

    try:
        results = await cache.lookup(query)
        latency_ms = (time.perf_counter() - start) * 1000

        log.info(
            "cache_lookup",
            user_id=user_id,
            query_length=len(query),
            cache_hit=results is not None,
            latency_ms=round(latency_ms, 2),
            result_count=len(results) if results else 0
        )
        return results

    except Exception as e:
        log.error("cache_error", error=str(e), query=query[:50])
        raise
```

## Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    try:
        # Check Valkey connection
        client.ping()

        # Check index exists
        info = client.ft("idx:docs").info()

        return {
            "status": "healthy",
            "valkey": "connected",
            "index_docs": info["num_docs"],
            "cache_hit_rate": f"{metrics.hit_rate:.1%}",
            "avg_latency_ms": round(metrics.avg_hit_latency, 2)
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Alert Thresholds

Metric| Warning| Critical  
---|---|---  
Cache Hit Rate| <70%| <50%  
Search Latency p99| >50ms| >200ms  
Memory Usage| >75%| >90%  
Error Rate| >1%| >5%  
  
### 🎉 Cookbook Complete

You've learned the fundamentals of RAG with Valkey. Ready to build?

[Try the Demo →](</demo/rag-pipeline.html>) [View on GitHub →](<https://github.com/meet-bhagdev/valkeyforai>)

[← Scaling](<05-scaling-production.html>) [All Cookbooks](</cookbooks/rag-pipelines/>)
