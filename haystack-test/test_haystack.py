"""
Haystack + Valkey — local test
Run: python3 test_haystack.py

Prerequisites:
  docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
  pip install haystack-ai valkey-haystack sentence-transformers
"""

from haystack_integrations.document_stores.valkey import ValkeyDocumentStore
from haystack_integrations.components.retrievers.valkey import ValkeyEmbeddingRetriever
from haystack.components.embedders import (
    SentenceTransformersDocumentEmbedder,
    SentenceTransformersTextEmbedder,
)
from haystack import Document

# ── 1. Connect to Valkey ──────────────────────────────────────────────────────
document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="test_docs",
    embedding_dim=768,        # must match the model below
    distance_metric="cosine",
)
print(f"Connected. Documents in store: {document_store.count_documents()}")

# ── 2. Index documents ────────────────────────────────────────────────────────
docs = [
    Document(content="Valkey is a high-performance in-memory data store."),
    Document(content="Haystack is an open-source LLM framework by deepset."),
    Document(content="Vector search finds semantically similar documents."),
    Document(content="ValkeyDocumentStore integrates directly with Haystack pipelines."),
    Document(content="Cosine similarity measures the angle between two embedding vectors."),
]

print("\nEmbedding documents (first run downloads ~420MB model)...")
doc_embedder = SentenceTransformersDocumentEmbedder(
    model="sentence-transformers/all-mpnet-base-v2"
)
doc_embedder.warm_up()
docs_with_embeddings = doc_embedder.run(docs)["documents"]
document_store.write_documents(docs_with_embeddings, policy="overwrite")
print(f"Indexed {document_store.count_documents()} documents")

# ── 3. Query ──────────────────────────────────────────────────────────────────
text_embedder = SentenceTransformersTextEmbedder(
    model="sentence-transformers/all-mpnet-base-v2"
)
text_embedder.warm_up()
retriever = ValkeyEmbeddingRetriever(document_store=document_store, top_k=2)

queries = [
    "What is Valkey used for?",
    "How does Haystack work?",
    "How do I do vector similarity search?",
]

print()
for query in queries:
    query_embedding = text_embedder.run(query)["embedding"]
    results = retriever.run(query_embedding=query_embedding)
    print(f"Q: {query}")
    for doc in results["documents"]:
        print(f"  {doc.score:.3f} | {doc.content}")
    print()
