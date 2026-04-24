"""Integration tests for Conversation Memory - Semantic Memory.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_03_semantic_memory(raw_client):
    """Run all code blocks from: Semantic Memory."""

    # --- Block 1 ---
    from glide import (
        GlideClient, GlideClientConfiguration, NodeAddress,
        ft, TagField, NumericField,
        VectorField, VectorAlgorithm, VectorFieldAttributesHnsw,
        VectorType, DistanceMetricType,
        FtCreateOptions, DataType,
    )

    async def create_memory_index(client):
        # Check if index already exists
        existing = await ft.list(client)
        names = [n.decode() for n in existing]
        if "memory_idx" in names:
            return

        hnsw = VectorFieldAttributesHnsw(
            dimensions=1536,  # Titan embedding size
            distance_metric=DistanceMetricType.COSINE,
            type=VectorType.FLOAT32,
        )

        await ft.create(
            client, "memory_idx",
            schema=[
                TagField("$.session_id", alias="session_id"),
                TagField("$.role", alias="role"),
                TagField("$.user_id", alias="user_id"),
                NumericField("$.timestamp", alias="timestamp"),
                VectorField("$.embedding", VectorAlgorithm.HNSW,
                            alias="embedding", attributes=hnsw),
            ],
            options=FtCreateOptions(data_type=DataType.JSON, prefixes=["mem:"]),
        )
        print("✅ Index created")

    # --- Block 2 ---
    import json, struct, time, uuid, boto3
    from glide import glide_json

    def get_embedding(text):
        """Get embedding from Bedrock Titan."""
        bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            body=json.dumps({"inputText": text}),
        )
        return json.loads(response["body"].read())["embedding"]


    async def store_memory(client, session_id, user_id, role, content):
        """Store a message with its embedding for semantic search."""
        embedding = get_embedding(content)
        doc_id = f"mem:{uuid.uuid4().hex[:12]}"

        doc = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "embedding": embedding,
        }

        await glide_json.set(client, doc_id, "$", json.dumps(doc))
        return doc_id

    # --- Block 3 ---
    async def search_memory(client, query, limit=5, user_id=None):
        """Find semantically similar messages across all sessions."""
        from glide import FtSearchOptions

        query_embedding = get_embedding(query)
        vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)

        # Build filter - optionally scope to a user
        filter_expr = "*"
        if user_id:
            filter_expr = f"@user_id:{{{user_id}}}"

        query_str = f"({filter_expr})==>[KNN {limit} @embedding $vec AS score]"

        result = await ft.search(
            client, "memory_idx", query_str,
            options=FtSearchOptions(params={"vec": vec_bytes}),
        )

        # Parse results
        memories = []
        if result and len(result) >= 2:
            for key, fields in result[1].items():
                doc = json.loads(fields[b"$"])
                score = 1.0 - float(fields.get(b"score", 1))
                memories.append({
                    "content": doc["content"],
                    "session_id": doc["session_id"],
                    "role": doc["role"],
                    "score": round(score, 3),
                })
        return memories

    # --- Block 4 ---
    async def demo():
        config = GlideClientConfiguration([NodeAddress("localhost", 6379)])
        client = await GlideClient.create(config)

        await create_memory_index(client)

        # Store memories from different sessions
        await store_memory(client, "sess_1", "alice", "user",
            "We deployed to ECS using a blue-green strategy")
        await store_memory(client, "sess_2", "alice", "assistant",
            "Valkey HNSW index provides sub-millisecond vector search")
        await store_memory(client, "sess_3", "alice", "user",
            "Our CI/CD pipeline runs on CodePipeline with canary deploys")

        # Search across all sessions
        results = await search_memory(client, "How do I deploy my service?")
        print("🔍 Results for 'How do I deploy my service?':")
        for r in results:
            print(f"   [{r['score']:.3f}] ({r['session_id']}) {r['content']}")

        # Output:
        # [0.847] (sess_1) We deployed to ECS using a blue-green strategy
        # [0.812] (sess_3) Our CI/CD pipeline runs on CodePipeline with canary deploys
        # [0.234] (sess_2) Valkey HNSW index provides sub-millisecond vector search

