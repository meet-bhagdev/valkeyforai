"""Integration tests for LangChain - Semantic Search.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_semantic_search(raw_client):
    """Run all code blocks from: Semantic Search."""

    # --- Block 1 ---
    from langgraph_checkpoint_aws import ValkeyStore
    from langchain_aws import BedrockEmbeddings

    # Amazon Titan embeddings - 1536 dimensions
    embeddings = BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0",
        region_name="us-west-2",
    )

    # ValkeyStore with HNSW vector index
    store = ValkeyStore.from_conn_string(
        "valkey://localhost:6379",
        index={
            "collection_name": "semantic_cache",
            "dims": 1536,
            "embed": embeddings,
            "fields": ["text"],
            "index_type": "hnsw",
            "distance_metric": "COSINE",
        },
        ttl={"default_ttl": 60.0},  # 60 minutes
    )
    store.setup()  # Creates the FT index

    # --- Block 2 ---
    # Search with a paraphrased query
    results = store.search(
        ("help-desk",),  # namespace prefix
        query="I forgot my password, help!",
        limit=3,
    )

    for r in results:
        print(f"Score: {r.score:.3f} - {r.value['text']}")

    # Output:
    # Score: 0.943 - How do I reset my password?
    # Score: 0.412 - How do I connect to the VPN?

    # --- Block 3 ---
    # Index creation (once)
    FT.CREATE semantic_cache_idx ON JSON PREFIX 1 "store:semantic_cache:"
      SCHEMA $.text AS text TAG
             $.embedding AS embedding VECTOR HNSW 6
               TYPE FLOAT32 DIM 1536 DISTANCE_METRIC COSINE

    # Store document
    JSON.SET store:semantic_cache:help-desk:passwords:q1 $ '{...}'
    EXPIRE store:semantic_cache:help-desk:passwords:q1 3600

    # Vector search
    FT.SEARCH semantic_cache_idx
      "(*)==>[KNN 3 @embedding $vec AS score]"
      PARAMS 2 vec <binary_vector>
      LIMIT 0 3

