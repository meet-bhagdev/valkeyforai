## How RAG Works

```
User question
  → embed question
  → find similar docs in Valkey (KNN)
  → inject docs into prompt
  → LLM generates grounded answer
```

Valkey handles the retrieval step - sub-millisecond KNN over your document embeddings.

## Step 1: Indexing Pipeline

Run this once to embed and store your documents:

```python
import os
from dotenv import load_dotenv

load_dotenv()

from haystack import Pipeline, Document
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.components.writers import DocumentWriter
from haystack_integrations.document_stores.valkey import ValkeyDocumentStore

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="rag_docs",
    embedding_dim=768,
    distance_metric="cosine",
)

indexing_pipeline = Pipeline()
indexing_pipeline.add_component(
    "embedder",
    SentenceTransformersDocumentEmbedder(model="sentence-transformers/all-mpnet-base-v2")
)
indexing_pipeline.add_component("writer", DocumentWriter(document_store=document_store))
indexing_pipeline.connect("embedder.documents", "writer.documents")

# Your documents - swap this for file loaders, web crawlers, etc.
docs = [
    Document(content="Valkey supports vector search natively via its module system."),
    Document(content="The ValkeyDocumentStore integrates directly with Haystack pipelines."),
    Document(content="Cosine similarity measures the angle between two embedding vectors."),
    Document(content="RAG grounds LLM responses in retrieved facts, reducing hallucinations."),
    Document(content="Haystack pipelines are composable - swap any component without rewriting the rest."),
]

indexing_pipeline.run({"embedder": {"documents": docs}})
print(f"Indexed {document_store.count_documents()} documents")
```

## Step 2: Query Pipeline

Wire together embedding, retrieval, prompt building, and LLM generation:

```python
from haystack import Pipeline
from haystack.utils import Secret
from haystack.dataclasses import ChatMessage
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.builders import ChatPromptBuilder
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack_integrations.components.retrievers.valkey import ValkeyEmbeddingRetriever

prompt_template = [
    ChatMessage.from_system(
        "Answer the question using only the provided context. "
        "If the context doesn't contain the answer, say 'I don't know'."
    ),
    ChatMessage.from_user(
        "Context:\n{% for doc in documents %}{{ doc.content }}\n{% endfor %}\n"
        "Question: {{query}}"
    ),
]

query_pipeline = Pipeline()
query_pipeline.add_component(
    "text_embedder",
    SentenceTransformersTextEmbedder(model="sentence-transformers/all-mpnet-base-v2")
)
query_pipeline.add_component(
    "retriever",
    ValkeyEmbeddingRetriever(document_store=document_store, top_k=3)
)
query_pipeline.add_component(
    "prompt_builder",
    ChatPromptBuilder(template=prompt_template, required_variables=["query", "documents"])
)
query_pipeline.add_component(
    "generator",
    OpenAIChatGenerator(
        api_key=Secret.from_env_var("OPENAI_API_KEY"),
        model="gpt-4o"
    )
)

query_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
query_pipeline.connect("retriever.documents", "prompt_builder.documents")
query_pipeline.connect("prompt_builder.messages", "generator.messages")
```

## Step 3: Ask a Question

```python
query = "How does Valkey integrate with Haystack?"

result = query_pipeline.run({
    "text_embedder": {"text": query},
    "prompt_builder": {"query": query},
})

print(result["generator"]["replies"][0].content)
```

Output:

```
The ValkeyDocumentStore integrates directly with Haystack pipelines,
allowing you to store document embeddings in Valkey and retrieve them
using the ValkeyEmbeddingRetriever component.
```

## Pipeline Architecture

The indexing and query pipelines are intentionally separate. You index once (or on a schedule), then query thousands of times. Valkey's in-memory KNN means retrieval adds ~1ms to your total latency - negligible compared to the LLM call.

| Stage | Component | What it does |
|-------|-----------|-------------|
| Index | `SentenceTransformersDocumentEmbedder` | Generates 768-dim embeddings for each doc |
| Index | `DocumentWriter` | Writes docs + embeddings to Valkey |
| Query | `SentenceTransformersTextEmbedder` | Embeds the user's question |
| Query | `ValkeyEmbeddingRetriever` | KNN search - returns top-k similar docs |
| Query | `ChatPromptBuilder` | Injects retrieved docs into the prompt |
| Query | `OpenAIChatGenerator` | Generates the final grounded answer |

## Swap the Embedding Model

Any Haystack-compatible embedder works. Just keep `embedding_dim` consistent between the document store and both embedders:

```python
# OpenAI embeddings (1536-dim)
from haystack.components.embedders import OpenAIDocumentEmbedder, OpenAITextEmbedder

document_store = ValkeyDocumentStore(
    nodes_list=[("localhost", 6379)],
    index_name="rag_docs_openai",
    embedding_dim=1536,  # text-embedding-3-small
    distance_metric="cosine",
)
```
