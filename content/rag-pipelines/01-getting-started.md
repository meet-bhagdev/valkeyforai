[← All RAG Cookbooks](/cookbooks/rag-pipelines/)

# Getting Started with RAG Cache

Set up Valkey, create your first vector index, and run semantic search queries.

## Step 1: Start Valkey with Docker

The easiest way to get started is with Docker. Valkey Bundle includes vector search capabilities out of the box.

```bash
# Pull and run Valkey with search module
docker run -d --name valkey \
  -p 6379:6379 \
  valkey/valkey-bundle:9-alpine

# Verify it's running
docker exec -it valkey valkey-cli ping
# Expected: PONG
```

## Step 2: Create a Vector Search Index

Use FT.CREATE to define a schema with tag fields and a vector field for embeddings.

```bash
FT.CREATE idx:docs ON HASH PREFIX 1 "doc:"
  SCHEMA
    content TAG
    section TAG
    embedding VECTOR HNSW 6
      TYPE FLOAT32
      DIM 1536
      DISTANCE_METRIC COSINE
```

**Parameters:** DIM=1536 matches OpenAI's text-embedding-3-small. Adjust for your embedding model.

## Step 3: Store Document Chunks

Store your document chunks as hashes with their embeddings.

```python
# Python example
import os
from dotenv import load_dotenv

load_dotenv()

import valkey
import numpy as np

client = valkey.Valkey(host='localhost', port=6379)

# Generate embedding (use your embedding provider)
embedding = get_embedding("Your document text here...")
embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()

# Store the document
client.hset("doc:chunk_001", mapping={
    "content": "Your document text here...",
    "section": "Introduction",
    "embedding": embedding_bytes,
})
```

## Step 4: Run a Semantic Search

Use FT.SEARCH with KNN to find the most similar documents.

```python
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
```

## Step 5: Complete Python Example

Here's a full working example with OpenAI embeddings:

```python
import valkey
import numpy as np
from openai import OpenAI

# Initialize clients
openai = OpenAI()
vk = valkey.Valkey(host='localhost', port=6379, decode_responses=False)

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
```

**✓ What you've learned:**

- Starting Valkey with Docker
- Creating a vector search index with FT.CREATE
- Storing documents with embeddings
- Running KNN semantic search queries

[Next: Semantic Caching →](02-semantic-caching.html)
