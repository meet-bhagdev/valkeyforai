"""Integration tests for RAG Pipelines - Vector Search for RAG.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_vector_search(raw_client):
    """Run all code blocks from: Vector Search for RAG."""

    # --- Block 1 ---
    from valkey.commands.search.query import Query

    def hybrid_search(query_text, category=None, date_range=None, k=5):
        # Build filter
        filters = []
        if category:
            filters.append(f"@category:{{{category}}}")
        if date_range:
            filters.append(f"@date:[{date_range[0]} {date_range[1]}]")

        filter_str = " ".join(filters) if filters else "*"

        # Build query
        query_embedding = get_embedding(query_text)
        query_bytes = np.array(query_embedding, dtype=np.float32).tobytes()

        q = Query(f"({filter_str})=>[KNN {k} @embedding $vec AS score]")
        q.return_fields("content", "category", "score")
        q.dialect(2)

        return client.ft("idx:docs").search(q, {"vec": query_bytes})

