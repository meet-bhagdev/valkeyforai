## Pattern 1: Threshold Tuning

The `defaultThreshold` controls the trade-off between hit rate and answer quality. It is a **cosine distance** (0–2 scale).

| Threshold | Hit Rate | Quality Risk | Best For |
|-----------|----------|--------------|----------|
| `0.05` | Low (~20%) | Very low | Medical, legal, financial |
| `0.10` | Medium (~35%) | Low | High-accuracy chatbots |
| `0.15` | Balanced (~50%) | Low | General purpose - start here |
| `0.20` | High (~65%) | Medium | FAQ bots, support |
| `0.30+` | Very high (~75%+) | High | Not recommended unless monitored |

To find the right threshold, run a sample of your real queries through the cache and inspect the similarity scores:

```typescript
import { SemanticCache } from '@betterdb/semantic-cache';

// Use a low threshold (wide net) to collect score data
const evalCache = new SemanticCache({
  client,
  embedFn,
  defaultThreshold: 0.50, // catch everything for analysis
});
await evalCache.initialize();

const testPrompts = [
  'What is Valkey?',
  'Can you explain Valkey?',     // should match → expect low score
  'How do I set a key in Redis?', // different intent → expect high score
  'Valkey vs Redis comparison',   // related but different → borderline
];

for (const prompt of testPrompts) {
  const result = await evalCache.check(prompt);
  if (result.similarity !== undefined) {
    console.log(`score=${result.similarity.toFixed(4)}  prompt="${prompt}"`);
  }
}
// score=0.0821  prompt="Can you explain Valkey?"
// score=0.3142  prompt="How do I set a key in Redis?"
// score=0.2205  prompt="Valkey vs Redis comparison"
```

Set your threshold between the highest acceptable hit and the lowest unacceptable hit.

---

## Pattern 2: Handling Uncertain Hits

When a prompt falls in the uncertainty band - slightly above the threshold - `cache.check()` returns `confidence: 'uncertain'`. Three strategies:

**Accept and monitor** - return the cached response but track it separately via the `result: 'uncertain_hit'` Prometheus label. Review periodically.

```typescript
const result = await cache.check(prompt);

if (result.hit) {
  if (result.confidence === 'uncertain') {
    metrics.increment('cache.uncertain_hit'); // your own counter
  }
  return result.response!;
}
```

**Fall back to LLM** - treat uncertain hits as misses. Use the fresh LLM response to overwrite the cache entry.

```typescript
const result = await cache.check(prompt);

if (result.hit && result.confidence === 'high') {
  return result.response!;
}

// Miss or uncertain - call LLM
const response = await callLlm(prompt);
await cache.store(prompt, response); // overwrites uncertain entry
return response;
```

**Prompt for feedback** - in user-facing applications, show the cached response but collect a signal.

```typescript
if (result.hit && result.confidence === 'uncertain') {
  return {
    response: result.response,
    showFeedback: true, // render thumbs up/down in the UI
  };
}
```

A high rate of uncertain hits (visible in `semantic_cache_requests_total{result="uncertain_hit"}`) indicates the threshold may be too loose.

---

## Pattern 3: Per-Category Thresholds

Different query categories can have different accuracy requirements. Use `categoryThresholds` to override the default per-category:

```typescript
const cache = new SemanticCache({
  client,
  embedFn,
  defaultThreshold: 0.15,
  categoryThresholds: {
    'medical': 0.05,    // very strict - health information must be accurate
    'faq':     0.25,    // relaxed - FAQ answers are safe to generalize
    'support': 0.20,    // moderate - support answers are usually reusable
  },
});

// Pass category on each call
const result = await cache.check(prompt, { category: 'medical' });
await cache.store(prompt, response, { category: 'medical' });
```

The category is stored as a TAG field in Valkey and is also emitted as a label on all Prometheus metrics.

---

## Pattern 4: TTL Strategies

```typescript
// Fixed TTL - simple, applied at store time
await cache.store(prompt, response, { ttl: 3600 }); // 1 hour

// Use defaultTtl in the constructor for a global default
const cache = new SemanticCache({
  client, embedFn,
  defaultTtl: 86400, // 24 hours
});

// Per-category TTL (set at store time, overrides default)
await cache.store(prompt, response, {
  category: 'real-time',
  ttl: 300, // 5 minutes for time-sensitive data
});
```

| Category | Recommended TTL | Reason |
|----------|----------------|--------|
| General facts | 86400 (24h) | Stable information |
| Product info | 3600 (1h) | Changes occasionally |
| Real-time data | 300 (5min) | Prices, weather, status |
| Conversation | 1800 (30min) | Session-scoped |

---

## Pattern 5: Cache Invalidation

```typescript
// Invalidate a specific entry by its exact prompt
const key = await cache.store('What is the price of product X?', response);
await cache.invalidate(`@key:{${key}}`);

// Invalidate all entries for a category
await cache.invalidate('@category:{pricing}');

// Invalidate all entries for a model (if you store model as a custom field)
// Use cache.flush() to drop everything and rebuild from scratch
await cache.flush();
await cache.initialize(); // rebuild the index
```

> **Note:** `invalidate()` accepts any `valkey-search` filter expression. See the [Valkey search query syntax](https://valkey.io/docs/topics/valkey-search-query-syntax/) for full filter options.

---

## Pattern 6: Prometheus Metrics

All metrics are prefixed with `semantic_cache_` by default (configurable via `telemetry.metricsPrefix`).

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `semantic_cache_requests_total` | Counter | `cache_name`, `result`, `category` | Total requests. `result`: `hit`, `miss`, `uncertain_hit` |
| `semantic_cache_similarity_score` | Histogram | `cache_name`, `category` | Cosine distance scores for lookups with candidates |
| `semantic_cache_operation_duration_seconds` | Histogram | `cache_name`, `operation` | Duration per operation (`check`, `store`, `invalidate`, `initialize`) |
| `semantic_cache_embedding_duration_seconds` | Histogram | `cache_name` | Embedding function call duration |

Expose them via a `/metrics` endpoint:

```typescript
import { register } from 'prom-client';
import express from 'express';

const app = express();

app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});
```

Key dashboards to build:

```
# Hit rate over time
rate(semantic_cache_requests_total{result="hit"}[5m])
  / rate(semantic_cache_requests_total[5m])

# P95 check latency
histogram_quantile(0.95, rate(semantic_cache_operation_duration_seconds_bucket{operation="check"}[5m]))

# Uncertain hit fraction
rate(semantic_cache_requests_total{result="uncertain_hit"}[5m])
  / rate(semantic_cache_requests_total[5m])
```

---

## Production Checklist

| Area | Recommendation |
|------|---------------|
| Threshold | Start at `0.15`, tune with real query samples |
| Uncertain hits | Track the `uncertain_hit` label; adjust threshold if > 10% |
| TTL | Set `defaultTtl`; override per-category for time-sensitive data |
| Memory | Set `maxmemory-policy allkeys-lru` in Valkey config |
| Invalidation | Use category TAGs at write time for targeted invalidation |
| Metrics | Expose `/metrics` and alert on hit rate drop > 20% |
| Cluster | Avoid `flush()` in cluster mode - SCAN only covers one node |
| Streaming | Accumulate full response before calling `store()` |
