[← All RAG Cookbooks](</cookbooks/rag-pipelines/>)

# Semantic Caching Patterns

Cache LLM responses by semantic similarity — not just exact matches. Save costs and reduce latency.

## Why Semantic Caching?

Traditional caching requires exact query matches. But users ask the same question in different ways:

  * "How do I reset my password?"
  * "I forgot my password, help"
  * "Password reset instructions"

Semantic caching matches by meaning, so all three queries hit the same cached response.

## Create a Cache Index

```bash
FT.CREATE idx:llm_cache ON HASH PREFIX 1 "cache:"
  SCHEMA
    query TAG
    response TAG
    embedding VECTOR HNSW 6
      TYPE FLOAT32
      DIM 1536
      DISTANCE_METRIC COSINE
```

## Cache Lookup Pattern

```python
async def semantic_cache_lookup(query: str, threshold: float = 0.92):
    # Embed the query
    query_embedding = await get_embedding(query)
    query_bytes = np.array(query_embedding, dtype=np.float32).tobytes()

    # Search for similar cached queries
    results = client.execute_command(
        'FT.SEARCH', 'idx:llm_cache',
        '*=>[KNN 1 @embedding $vec AS score]',
        'PARAMS', '2', 'vec', query_bytes,
        'RETURN', '2', 'response', 'score',
        'DIALECT', '2'
    )

    if results[0] > 0:
        similarity = 1 - float(results[2][3])  # Convert distance to similarity
        if similarity >= threshold:
            return results[2][1]  # Return cached response

    return None  # Cache miss
```

## Similarity Threshold Tuning

The threshold determines how similar queries must be to trigger a cache hit:

Threshold| Behavior| Use Case  
---|---|---  
**0.95+**|  Very strict — near-identical queries only| Legal, medical, compliance  
**0.90-0.95**|  Balanced — captures paraphrases| General Q&A;, support bots  
**0.85-0.90**|  Loose — similar topics match| Conversational AI, brainstorming  
**< 0.85**| Very loose — may return unrelated answers| Not recommended  
  
**💡 Tip:** Start with 0.92 and adjust based on your cache hit rate and answer quality. Monitor false positives closely. 

## TTL Strategies

Different content needs different cache lifetimes:

```python
# Store with TTL
def cache_response(query, response, ttl_seconds=3600):
    key = f"cache:{hash(query)[:16]}"
    embedding = get_embedding(query)
    client.hset(key, mapping={
        "query": query,
        "response": response,
        "embedding": np.array(embedding, dtype=np.float32).tobytes()
    })
    client.expire(key, ttl_seconds)

# Different TTLs by content type
TTL_CONFIG = {
    "factual": 86400,   # 24 hours - stable facts
    "news": 3600,        # 1 hour - current events
    "weather": 1800,     # 30 min - frequently changes
    "stock": 60,         # 1 min - real-time data
}
```

## Complete Caching Class

```python
class SemanticCache:
    def __init__(self, threshold=0.92, default_ttl=3600):
        self.client = valkey.Valkey(decode_responses=False)
        self.threshold = threshold
        self.default_ttl = default_ttl
        self._create_index()

    def _create_index(self):
        try:
            self.client.execute_command(
                'FT.CREATE', 'idx:cache',
                'ON', 'HASH', 'PREFIX', '1', 'cache:',
                'SCHEMA',
                'query', 'TAG',
                'response', 'TAG',
                'embedding', 'VECTOR', 'HNSW', '6',
                'TYPE', 'FLOAT32',
                'DIM', '1536',
                'DISTANCE_METRIC', 'COSINE'
            )
        except:
            pass

    async def get(self, query: str) -> str | None:
        emb = await get_embedding(query)
        vec = np.array(emb, dtype=np.float32).tobytes()

        results = self.client.execute_command(
            'FT.SEARCH', 'idx:cache',
            '*=>[KNN 1 @embedding $v AS s]',
            'PARAMS', '2', 'v', vec,
            'DIALECT', '2'
        )

        if results[0] > 0 and (1 - float(results[2][3])) >= self.threshold:
            return results[2][1].decode()
        return None

    async def set(self, query: str, response: str, ttl: int = None):
        key = f"cache:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
        emb = await get_embedding(query)
        self.client.hset(key, mapping={
            "query": query,
            "response": response,
            "embedding": np.array(emb, dtype=np.float32).tobytes()
        })
        self.client.expire(key, ttl or self.default_ttl)
```

**⚠️ Watch out:** Semantic caching can return cached answers for queries that seem similar but need different responses. Always validate with real user queries before production. 

[← Getting Started](<01-getting-started.html>) [Next: Vector Search →](<03-vector-search.html>)
