"""Integration tests for RAG Pipelines - Semantic Caching for RAG.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_02_semantic_caching(raw_client):
    """Run all code blocks from: Semantic Caching for RAG."""

    # --- Block 1 ---
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

    # --- Block 2 ---
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

    # --- Block 3 ---
    class SemanticCache:
        def __init__(self, threshold=0.92, default_ttl=3600):
            self.client = raw_client
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

