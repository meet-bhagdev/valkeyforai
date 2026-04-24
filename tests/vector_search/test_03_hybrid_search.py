"""Integration tests for Vector Search - Hybrid Search.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_hybrid_search(raw_client):
    """Run all code blocks from: Hybrid Search."""

    # --- Block 1 ---
    import numpy as np

    client = raw_client

    def vec_to_bytes(vec):
        return np.array(vec, dtype=np.float32).tobytes()

    # Create index with VECTOR + TAG + NUMERIC + TEXT fields
    try:
        client.execute_command(
            "FT.CREATE", "articles_idx",
            "SCHEMA",
            "title", "TAG",
            "category", "TAG",
            "year", "NUMERIC",
            "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", "4",
            "DISTANCE_METRIC", "COSINE",
        )
        print("Index created with TAG + NUMERIC + VECTOR")
    except valkey.ResponseError as e:
        print(f"Index exists: {e}")

    # --- Block 2 ---
    query_vec = vec_to_bytes([0.88, 0.1, 0.2, 0.35])

    # TAG filter: @category:{tech}
    # Combined with KNN: @category:{tech}=>[KNN 3 @embedding $query_vec]
    results = client.execute_command(
        "FT.SEARCH", "articles_idx",
        "@category:{tech}=>[KNN 3 @embedding $query_vec]",
        "PARAMS", "2", "query_vec", query_vec,
        "DIALECT", "2",
    )

    print(f"Tech articles (KNN): {results[0]} results")
    for i in range(1, len(results), 2):
        fields = results[i + 1]
        fd = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
        print(f"  {results[i]}: {fd.get('title')} [{fd.get('category')}]")

    # Only returns tech articles - food and finance are excluded!

    # --- Block 3 ---
    # NUMERIC filter: @year:[2024 +inf]
    results = client.execute_command(
        "FT.SEARCH", "articles_idx",
        "@year:[2024 +inf]=>[KNN 3 @embedding $query_vec]",
        "PARAMS", "2", "query_vec", query_vec,
        "DIALECT", "2",
    )

    print(f"\nArticles from 2024+: {results[0]} results")
    for i in range(1, len(results), 2):
        fields = results[i + 1]
        fd = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
        print(f"  {results[i]}: {fd.get('title')} ({fd.get('year')})")

    # --- Block 4 ---
    # Combine multiple filters
    results = client.execute_command(
        "FT.SEARCH", "articles_idx",
        "(@category:{tech} @year:[2024 +inf])=>[KNN 3 @embedding $query_vec]",
        "PARAMS", "2", "query_vec", query_vec,
        "DIALECT", "2",
    )

    print(f"\nTech articles from 2024+: {results[0]} results")
    for i in range(1, len(results), 2):
        fields = results[i + 1]
        fd = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
        print(f"  {results[i]}: {fd.get('title')} [{fd.get('category')}, {fd.get('year')}]")

