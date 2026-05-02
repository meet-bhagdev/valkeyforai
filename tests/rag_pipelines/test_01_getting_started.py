"""Integration tests for RAG Pipelines - Getting Started with RAG.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(raw_client):
    """Run all code blocks from: Getting Started with RAG."""

    # --- Block 1 ---
    # Python example


    import numpy as np

    client = raw_client

    # Generate embedding (use your embedding provider)
    embedding = get_embedding("Your document text here...")
    embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()

    # Store the document
    client.hset("doc:chunk_001", mapping={
        "content": "Your document text here...",
        "section": "Introduction",
        "embedding": embedding_bytes,
    })

    # --- Block 2 ---
    # Generate query embedding
    query = "How do I create an index?"
    query_embedding = get_embedding(query)
    query_bytes = np.array(query_embedding, dtype=np.float32).tobytes()

    # KNN search for top 5 matches
    results = client.execute_command(
        'FT.SEARCH', 'idx:docs',
        '*=>[KNN 5 @embedding $vec AS score]',
        'PARAMS', '2', 'vec', query_bytes,
        'RETURN', '3', 'content', 'section', 'score',
        'DIALECT', '2'
    )
    print(f"Found {results[0]} results")

    # --- Block 3 ---
    import numpy as np
    from openai import OpenAI

    # Initialize clients
    openai = OpenAI()
    vk = raw_client

    def get_embedding(text):
        response = openai.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    # Create index (run once)
    try:
        vk.execute_command(
            'FT.CREATE', 'idx:docs',
            'ON', 'HASH', 'PREFIX', '1', 'doc:',
            'SCHEMA',
            'content', 'TAG',
            'embedding', 'VECTOR', 'HNSW', '6',
            'TYPE', 'FLOAT32', 'DIM', '1536',
            'DISTANCE_METRIC', 'COSINE'
        )
    except:
        pass  # Index exists

    # Store a document
    doc_text = "Valkey supports HNSW indexes for fast vector search."
    emb = get_embedding(doc_text)
    vk.hset("doc:1", mapping={
        "content": doc_text,
        "embedding": np.array(emb, dtype=np.float32).tobytes()
    })

    # Search
    query_emb = get_embedding("How does vector search work?")
    results = vk.execute_command(
        'FT.SEARCH', 'idx:docs',
        '*=>[KNN 3 @embedding $vec AS score]',
        'PARAMS', '2', 'vec',
        np.array(query_emb, dtype=np.float32).tobytes(),
        'DIALECT', '2'
    )
    print(results)

