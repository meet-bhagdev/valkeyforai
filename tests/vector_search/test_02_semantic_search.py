"""Integration tests for Vector Search - Semantic Search with Embeddings.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_02_semantic_search(raw_client):
    """Run all code blocks from: Semantic Search with Embeddings."""

    # --- Block 1 ---
    try:
        client.execute_command(
            "FT.CREATE", "semantic_idx",
            "SCHEMA",
            "content", "TAG",
            "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(EMBEDDING_DIM),
            "DISTANCE_METRIC", "COSINE",
        )
        print("Index created")
    except valkey.ResponseError:
        print("Index already exists")

    # --- Block 2 ---
    def get_embedding(text: str) -> bytes:
        """Get embedding from OpenAI and return as binary FLOAT32."""
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        vec = response.data[0].embedding  # list of 1536 floats
        return np.array(vec, dtype=np.float32).tobytes()

    # Sample documents
    docs = [
        "Valkey is an open-source in-memory data store forked from Redis",
        "Vector similarity search finds documents by semantic meaning",
        "Machine learning models convert text into numerical embeddings",
        "Python is the most popular language for AI development",
        "HNSW algorithm provides fast approximate nearest neighbor search",
        "Kubernetes orchestrates containerized applications at scale",
        "LLMs like GPT-4 generate human-like text responses",
        "Rate limiting protects APIs from excessive usage",
    ]

    # Embed and store each document
    for i, text in enumerate(docs):
        embedding_bytes = get_embedding(text)
        client.hset(f"doc:{i}", mapping={
            "content": text,
            "embedding": embedding_bytes,
        })
        print(f"Stored doc:{i}: {text[:50]}...")

    print(f"\nStored {len(docs)} documents with embeddings")

    # --- Block 3 ---
    def semantic_search(query: str, k: int = 3):
        """Search for documents semantically similar to the query."""

        # Embed the query
        query_vec = get_embedding(query)

        # KNN search
        results = client.execute_command(
            "FT.SEARCH", "semantic_idx",
            f"*=>[KNN {k} @embedding $query_vec]",
            "PARAMS", "2", "query_vec", query_vec,
            "DIALECT", "2",
        )

        # Parse results
        matches = []
        for i in range(1, len(results), 2):
            doc_key = results[i]
            fields = results[i + 1]
            field_dict = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
            matches.append({
                "key": doc_key,
                "content": field_dict.get("content", ""),
                "score": field_dict.get("__embedding_score", "N/A"),
            })
        return matches

    # Try different queries
    queries = [
        "What is Valkey?",
        "How do I find similar documents?",
        "Tell me about large language models",
    ]

    for q in queries:
        print(f"\nQuery: '{q}'")
        for m in semantic_search(q, k=2):
            print(f"  → {m['content']} (score: {m['score']})")

