## The Problem

LLM API calls are expensive ($0.01-$0.10+ per call) and slow (1-10 seconds). Users often ask similar questions with different wording:

  * "What is Valkey?" → "Can you explain Valkey?" → "Tell me about Valkey"
  * All three should return the same cached answer

Exact-match caching (`GET cache:{hash}`) misses these. Semantic caching uses vector similarity to match by meaning.

## Architecture

```python
User: "Can you explain Valkey?"
        │
        ▼
   Embed query → [0.12, -0.45, ...]
        │
        ▼
   FT.SEARCH cache_idx KNN 1 → score 0.95
        │
        ├── score ≥ 0.90 → ✅ Cache HIT → return cached response
        └── score < 0.90 → ❌ Cache MISS → call LLM → cache result
```

## Step 1: Create the Cache Index

```python
import os
from dotenv import load_dotenv

load_dotenv()

from glide import (
    ft, VectorField, VectorAlgorithm, VectorFieldAttributesHnsw,
    VectorType, DistanceMetricType, NumericField,
    FtCreateOptions, DataType,
)

async def create_cache_index(client):
    existing = await ft.list(client)
    if b"cache_idx" in existing:
        return

    hnsw = VectorFieldAttributesHnsw(
        dimensions=1536,
        distance_metric=DistanceMetricType.COSINE,
        type=VectorType.FLOAT32,
    )
    await ft.create(
        client, "cache_idx",
        schema=[
            NumericField("$.created_at", alias="created_at"),
            VectorField("$.embedding", VectorAlgorithm.HNSW,
                        alias="embedding", attributes=hnsw),
        ],
        options=FtCreateOptions(data_type=DataType.JSON, prefixes=["llmcache:"]),
    )
```

## Step 2: The Cache Lookup

```python
import json, struct, hashlib, time
from glide import glide_json, FtSearchOptions

SIMILARITY_THRESHOLD = 0.90  # Tune this: higher = stricter matching

async def cache_lookup(client, query_embedding):
    """Check if a semantically similar query was already answered."""
    vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)

    result = await ft.search(
        client, "cache_idx",
        "(*)==>[KNN 1 @embedding $vec AS score]",
        options=FtSearchOptions(params={"vec": vec_bytes}),
    )

    if result and len(result) >= 2 and result[1]:
        for key, fields in result[1].items():
            score = 1.0 - float(fields[b"score"])
            if score >= SIMILARITY_THRESHOLD:
                doc = json.loads(fields[b"$"])
                return {"hit": True, "response": doc["response"], "score": score}

    return {"hit": False}
```

## Step 3: Store a Cache Entry

```python
async def cache_store(client, query, response, embedding, ttl=3600):
    """Cache an LLM response with its query embedding."""
    cache_id = hashlib.md5(query.encode()).hexdigest()[:12]
    key = f"llmcache:{cache_id}"

    doc = {
        "query": query,
        "response": response,
        "embedding": embedding,
        "created_at": time.time(),
    }
    await glide_json.set(client, key, "$", json.dumps(doc))
    await client.expire(key, ttl)  # Auto-expire stale cache
```

## Step 4: The Complete Cache-Aware Chat Function

```python
async def chat_with_cache(client, user_message):
    # 1. Embed the query
    embedding = get_embedding(user_message)

    # 2. Check semantic cache
    cached = await cache_lookup(client, embedding)
    if cached["hit"]:
        print(f"⚡ Cache HIT (similarity: {cached['score']:.3f})")
        return cached["response"]

    # 3. Cache miss - call the LLM
    print("🔄 Cache MISS - calling LLM...")
    response = call_llm(user_message)  # your LLM call here

    # 4. Store in cache for next time
    await cache_store(client, user_message, response, embedding)

    return response


# First call: cache miss, calls LLM (~2 seconds)
await chat_with_cache(client, "What is Valkey?")
# 🔄 Cache MISS - calling LLM...

# Second call: cache hit, instant (~3ms)
await chat_with_cache(client, "Can you explain Valkey?")
# ⚡ Cache HIT (similarity: 0.953)
```

## Tuning the Similarity Threshold

Threshold| Behavior| Use case  
---|---|---  
`0.98`| Near-exact match only| Factual queries where precision matters  
`0.92`| Same intent, different wording| General chatbot (recommended start)  
`0.85`| Broadly similar topics| FAQ-style bots with limited topics  
  
Start at 0.92 and adjust based on your false-positive rate.

## Cost Impact

With a 40% cache hit rate (typical for customer support):

Metric| Without cache| With semantic cache  
---|---|---  
LLM calls / 1000 requests| 1,000| 600  
Avg latency| ~2,000ms| ~1,200ms  
Cost (at $0.01/call)| $10.00| $6.00  
Cache lookup overhead| -| ~3ms  
  
## Valkey Commands Reference

Operation| Command| Latency  
---|---|---  
Cache lookup| `FT.SEARCH cache_idx KNN 1`| ~1-3ms  
Cache store| `JSON.SET llmcache:{id} $ '{...}'`| ~0.2ms  
Set TTL| `EXPIRE llmcache:{id} 3600`| ~0.1ms  
Invalidate entry| `DEL llmcache:{id}`| ~0.1ms  
Flush all cache| `FT.DROPINDEX cache_idx`| ~1ms  
  
**Next up:** We've covered conversation history, session management, semantic memory, and caching. In the final cookbook, we'll add agent state - checkpointing multi-step reasoning and logging tool calls with Valkey Streams.