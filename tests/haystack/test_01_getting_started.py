"""Integration tests for Haystack - Getting Started with Haystack + Valkey.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with Haystack + Valkey."""

    # --- Block 1 ---
    from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

    document_store = ValkeyDocumentStore(
        nodes_list=[("localhost", 6379)],
        index_name="my_documents",
        embedding_dim=768,        # must match your embedding model
        distance_metric="cosine", # cosine | l2 | ip
    )

    print(document_store.count_documents())  # 0

    # --- Block 2 ---
    from haystack import Document

    docs = [
        Document(content="Valkey is a high-performance in-memory data store."),
        Document(content="Haystack is an open-source LLM framework by deepset."),
        Document(content="Vector search finds semantically similar documents."),
    ]

    document_store.write_documents(docs)
    print(document_store.count_documents())  # 3

    # --- Block 3 ---
    from haystack.components.embedders import SentenceTransformersDocumentEmbedder

    doc_embedder = SentenceTransformersDocumentEmbedder(
        model="sentence-transformers/all-mpnet-base-v2"  # 768-dim, matches embedding_dim above
    )
    doc_embedder.warm_up()

    docs_with_embeddings = doc_embedder.run(docs)["documents"]
    document_store.write_documents(docs_with_embeddings, policy="overwrite")

    # --- Block 4 ---
    from haystack.components.embedders import SentenceTransformersTextEmbedder
    from haystack_integrations.components.retrievers.valkey import ValkeyEmbeddingRetriever

    text_embedder = SentenceTransformersTextEmbedder(
        model="sentence-transformers/all-mpnet-base-v2"
    )
    text_embedder.warm_up()

    retriever = ValkeyEmbeddingRetriever(document_store=document_store, top_k=2)

    query = "What is Valkey used for?"
    query_embedding = text_embedder.run(query)["embedding"]
    results = retriever.run(query_embedding=query_embedding)

    for doc in results["documents"]:
        print(f"Score: {doc.score:.3f} | {doc.content}")

