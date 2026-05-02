"""Integration tests for Vector Search - Getting Started with Vector Search.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(raw_client):
    """Run all code blocks from: Getting Started with Vector Search."""

    # --- Block 1 ---
    import numpy as np

    client = raw_client

    # Create an index with a 3-dimensional FLOAT32 vector field using HNSW
    # Syntax: FT.CREATE index SCHEMA field_name VECTOR HNSW num_params TYPE DIM DISTANCE_METRIC
    try:
        client.execute_command(
            "FT.CREATE", "doc_index",
            "SCHEMA",
            "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", "3",
            "DISTANCE_METRIC", "COSINE",
        )
        print("Index created.")
    except valkey.ResponseError as e:
        print(f"Index may already exist: {e}")

    # --- Block 2 ---
    # Helper: convert a list of floats to binary FLOAT32
    def vec_to_bytes(vec):
        return np.array(vec, dtype=np.float32).tobytes()

    # Store documents with embeddings using HSET
    documents = {
        "doc:1": {"content": "Valkey is a fast in-memory data store",
                  "embedding": vec_to_bytes([0.1, 0.2, 0.9])},
        "doc:2": {"content": "Python is great for machine learning",
                  "embedding": vec_to_bytes([0.8, 0.1, 0.3])},
        "doc:3": {"content": "Vector search finds similar items fast",
                  "embedding": vec_to_bytes([0.15, 0.25, 0.85])},
        "doc:4": {"content": "Neural networks power modern AI",
                  "embedding": vec_to_bytes([0.7, 0.2, 0.4])},
    }

    for key, fields in documents.items():
        client.hset(key, mapping=fields)
        print(f"Stored: {key}")

    print(f"Stored {len(documents)} documents")

    # --- Block 3 ---
    # Query vector - find documents similar to this
    query_vec = vec_to_bytes([0.12, 0.22, 0.88])

    # FT.SEARCH with KNN query
    # "*=>[KNN k @field $param]" finds the k nearest neighbors
    results = client.execute_command(
        "FT.SEARCH", "doc_index",
        "*=>[KNN 3 @embedding $query_vec]",
        "PARAMS", "2", "query_vec", query_vec,
        "DIALECT", "2",
    )

    # Parse results
    # results[0] = total count
    # results[1] = first doc key, results[2] = first doc fields
    # results[3] = second doc key, results[4] = second doc fields, etc.
    num_results = results[0]
    print(f"Found {num_results} results:\n")

    for i in range(1, len(results), 2):
        doc_key = results[i]
        fields = results[i + 1]
        # fields is a list of [field_name, value, field_name, value, ...]
        field_dict = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
        score = field_dict.get("__embedding_score", "N/A")
        content = field_dict.get("content", "")
        print(f"  {doc_key} (score: {score})")
        print(f"    {content}\n")

    # --- Block 4 ---
    # Get index metadata
    info = client.execute_command("FT.INFO", "doc_index")
    print(info)

