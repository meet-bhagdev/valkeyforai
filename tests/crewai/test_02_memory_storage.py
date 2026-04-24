"""Integration tests for CrewAI - Memory Storage.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_02_memory_storage(raw_client):
    """Run all code blocks from: Memory Storage."""

    # --- Block 1 ---
    from glide import (
        ft, VectorField, VectorAlgorithm, VectorFieldAttributesHnsw,
        VectorType, DistanceMetricType, NumericField, TextField,
        FtCreateOptions, DataType,
    )

    INDEX_NAME = "memory_idx"
    KEY_PREFIX = "memory:"
    VECTOR_DIM = 1536  # Amazon Titan embeddings

    async def ensure_index(client):
        # Check if index already exists
        existing = await ft.list(client)
        if INDEX_NAME.encode() in existing:
            return

        hnsw = VectorFieldAttributesHnsw(
            dimensions=VECTOR_DIM,
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
        )
        await ft.create(
            client, INDEX_NAME,
            schema=[
                TextField("$.scope", alias="scope"),
                TextField("$.categories_str", alias="categories_str"),
                NumericField("$.importance", alias="importance"),
                NumericField("$.created_at", alias="created_at"),
                VectorField("$.embedding", VectorAlgorithm.HNSW,
                            alias="embedding", attributes=hnsw),
            ],
            options=FtCreateOptions(data_type=DataType.JSON, prefixes=[KEY_PREFIX]),
        )

    # --- Block 2 ---
    from glide import glide_json

    async def store(client, record: MemoryRecord, ttl: int = 3600):
        key = f"{KEY_PREFIX}{record.id}"
        doc = serialize_record(record)
        await glide_json.set(client, key, "$", json.dumps(doc))
        await client.expire(key, ttl)

    # --- Block 3 ---
    JSON.SET memory:abc-123-def $ '{"id":"abc-123-def","content":"Always check for null...","embedding":[0.12,-0.45,...],...}'
    EXPIRE memory:abc-123-def 3600

    # --- Block 4 ---
    import struct

    async def recall(client, query_embedding: list[float], limit: int = 5):
        # Pack embedding to bytes for FT.SEARCH
        vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)

        result = await ft.search(
            client, INDEX_NAME,
            f"(*)=>[KNN {limit} @embedding $vec AS score]",
            options=FtSearchOptions(params={"vec": vec_bytes}),
        )

        # Parse results - score is cosine distance, convert to similarity
        memories = []
        if result and len(result) >= 2 and result[1]:
            for key, fields in result[1].items():
                doc = json.loads(fields[b"$"])
                score = 1.0 - float(fields[b"score"])
                memories.append((doc, score))

        return sorted(memories, key=lambda x: x[1], reverse=True)

    # --- Block 5 ---
    async def search(client, query_embedding, scope: str = None, categories: list = None, limit: int = 5):
        # Build filter expression
        filters = []
        if scope:
            escaped = scope.replace("/", "\\/")
            filters.append(f"@scope:{{{escaped}*}}")
        if categories:
            joined = "|".join(categories)
            filters.append(f"@categories_str:{{{joined}}}")

        filter_str = " ".join(filters) if filters else "*"
        query = f"({filter_str})=>[KNN {limit} @embedding $vec AS score]"

        vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)
        result = await ft.search(client, INDEX_NAME, query, options=FtSearchOptions(params={"vec": vec_bytes}))
        # ... parse results same as recall()

