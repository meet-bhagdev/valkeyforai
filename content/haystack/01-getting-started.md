Haystack is a framework for building RAG pipelines and search applications. Valkey replaces external vector databases with a single in-memory store that handles both document storage and similarity search, cutting infrastructure complexity and query latency.

## Prerequisites

- Docker installed (or a running Valkey instance)
- Python 3.10+ (required by `haystack-ai` and `valkey-haystack`)

## Step 1: Start Valkey

Vector search requires the `valkey-bundle` image, which includes the valkey-search module:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify it's running and the search module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# should include: name search
```

> **Note:** On first run you'll see `Error executing command: Index not found` - this is expected. The document store checks for an existing index, doesn't find one, then creates it automatically when you write your first documents.

## Step 2: Install Dependencies

```bash
pip install haystack-ai
pip install valkey-haystack
pip install sentence-transformers
```

The `valkey-haystack` package provides `ValkeyDocumentStore` and `ValkeyEmbeddingRetriever` as first-class Haystack components.

## Step 3: Connect to ValkeyDocumentStore

```python
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="my_documents",
    embedding_dim=768,        # must match your embedding model
    distance_metric="cosine", # cosine | l2 | ip
)

print(document_store.count_documents())  # 0
```

## Step 4: Write Documents

```python
from haystack import Document

docs = [
    Document(content="Valkey is a high-performance in-memory data store."),
    Document(content="Haystack is an open-source LLM framework by deepset."),
    Document(content="Vector search finds semantically similar documents."),
]

document_store.write_documents(docs)
print(document_store.count_documents())  # 3
```

## Step 5: Embed and Index Documents

Documents need embeddings before they can be searched by similarity. Use a `DocumentEmbedder` to generate and store them:

```python
from haystack.components.embedders import SentenceTransformersDocumentEmbedder

doc_embedder = SentenceTransformersDocumentEmbedder(
    model="sentence-transformers/all-mpnet-base-v2"  # 768-dim, matches embedding_dim above
)
doc_embedder.warm_up()

docs_with_embeddings = doc_embedder.run(docs)["documents"]
document_store.write_documents(docs_with_embeddings, policy="overwrite")
```

## Step 6: Run a Similarity Search

```python
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
```

Output:

```
Score: 0.921 | Valkey is a high-performance in-memory data store.
Score: 0.743 | Vector search finds semantically similar documents.
```

## How It Works Under the Hood

`ValkeyDocumentStore` stores each document's embedding as a Valkey hash and builds a vector index using Valkey's native vector search. Queries are single-hop - embed the query, run KNN against the index, get ranked results back. No external vector DB needed.

| Component | Role |
|-----------|------|
| `ValkeyDocumentStore` | Stores documents + embeddings, manages the vector index |
| `SentenceTransformersDocumentEmbedder` | Generates embeddings for documents at index time |
| `SentenceTransformersTextEmbedder` | Generates embedding for the query at search time |
| `ValkeyEmbeddingRetriever` | Runs KNN search and returns ranked documents |
