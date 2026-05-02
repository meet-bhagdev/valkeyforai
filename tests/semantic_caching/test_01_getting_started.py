"""Integration tests for Semantic Caching - Getting Started with Semantic Caching.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest
import valkey


def test_01_getting_started(raw_client, openai_client, openai_model):
    """Run all code blocks from: Getting Started with Semantic Caching."""

    # --- Block 1 ---
    import numpy as np
    import json
    import hashlib
    import time

    client = raw_client

    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIM = 1536
    SIMILARITY_THRESHOLD = 0.15  # COSINE distance: 0=identical, 2=opposite
    CACHE_TTL = 3600  # 1 hour

    # --- Block 2 ---
    def create_cache_index():
        """Create a vector index for the semantic cache."""
        try:
            client.execute_command(
                "FT.CREATE", "cache_idx",
                "SCHEMA",
                "prompt", "TAG",
                "response", "TAG",
                "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(EMBEDDING_DIM),
                "DISTANCE_METRIC", "COSINE",
            )
            print("Cache index created")
        except valkey.ResponseError:
            print("Cache index already exists")

    create_cache_index()

    # --- Block 3 ---
    def get_embedding(text: str) -> bytes:
        """Embed text using OpenAI and return as FLOAT32 bytes."""
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        vec = response.data[0].embedding
        return np.array(vec, dtype=np.float32).tobytes()

    # --- Block 4 ---
    def semantic_cache_lookup(prompt: str) -> dict:
        """Check if a semantically similar prompt is cached."""
        query_vec = get_embedding(prompt)

        # KNN search: find the 1 nearest cached prompt
        results = client.execute_command(
            "FT.SEARCH", "cache_idx",
            "*=>[KNN 1 @embedding $query_vec]",
            "PARAMS", "2", "query_vec", query_vec,
            "DIALECT", "2",
        )

        if results[0] > 0:
            fields = results[2]
            # Decode bytes from FT.SEARCH results (skip binary embedding field)
            field_dict = {}
            for j in range(0, len(fields), 2):
                k = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
                try:
                    v = fields[j+1].decode() if isinstance(fields[j+1], bytes) else fields[j+1]
                except UnicodeDecodeError:
                    v = fields[j+1]  # binary field (embedding)
                field_dict[k] = v
            score = float(field_dict.get("__embedding_score", "999"))

            if score < SIMILARITY_THRESHOLD:
                return {
                    "hit": True,
                    "response": field_dict.get("response", ""),
                    "cached_prompt": field_dict.get("prompt", ""),
                    "score": score,
                }

        return {"hit": False}

    def cache_response(prompt: str, response: str, embedding_bytes: bytes):
        """Store a prompt+response in the cache."""
        cache_key = f"cache:{hashlib.md5(prompt.encode()).hexdigest()}"
        client.hset(cache_key, mapping={
            "prompt": prompt,
            "response": response,
            "embedding": embedding_bytes,
            "created_at": str(time.time()),
        })
        client.expire(cache_key, CACHE_TTL)

    def ask_with_cache(prompt: str) -> dict:
        """Main function: check cache first, then call LLM if needed."""
        start = time.time()

        # 1. Check cache
        cache_result = semantic_cache_lookup(prompt)

        if cache_result["hit"]:
            elapsed = (time.time() - start) * 1000
            return {
                "response": cache_result["response"],
                "source": "cache",
                "similarity_score": cache_result["score"],
                "latency_ms": round(elapsed, 1),
            }

        # 2. Cache miss - call LLM
        llm_response = openai_client.chat.completions.create(
            model=openai_model,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = llm_response.choices[0].message.content

        # 3. Cache the response
        embedding_bytes = get_embedding(prompt)
        cache_response(prompt, answer, embedding_bytes)

        elapsed = (time.time() - start) * 1000
        return {
            "response": answer,
            "source": "llm",
            "latency_ms": round(elapsed, 1),
        }

    # --- Block 5 ---
    # First call - cache MISS (calls LLM)
    result1 = ask_with_cache("What is Valkey?")
    print(f"Source: {result1['source']}, Latency: {result1['latency_ms']}ms")
    # Source: llm, Latency: 1250.3ms

    # Second call - semantically similar - cache HIT!
    result2 = ask_with_cache("Can you explain what Valkey is?")
    print(f"Source: {result2['source']}, Latency: {result2['latency_ms']}ms")
    # Source: cache, Latency: 12.5ms  ← 100x faster!

    # Third call - different topic - cache MISS
    result3 = ask_with_cache("How do I cook pasta?")
    print(f"Source: {result3['source']}, Latency: {result3['latency_ms']}ms")
    # Source: llm, Latency: 980.7ms

