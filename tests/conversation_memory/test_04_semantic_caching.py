"""Integration tests for Conversation Memory - Semantic Caching.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_04_semantic_caching(raw_client):
    """Run all code blocks from: Semantic Caching."""

    # --- Block 1 ---
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

    # --- Block 2 ---
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

    # --- Block 3 ---
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

    # --- Block 4 ---
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

