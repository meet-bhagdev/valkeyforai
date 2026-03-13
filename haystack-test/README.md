# Haystack + Valkey — Local Test

## Setup

```bash
# 1. Start Valkey (bundle image required for vector search)
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest

# 2. Install deps (requires Python 3.10+)
python3.11 -m pip install haystack-ai valkey-haystack sentence-transformers

# 3. Run
python3.11 test_haystack.py
```

First run downloads the sentence-transformers model (~420MB). Subsequent runs are instant.

## Expected output

```
Connected. Documents in store: 0

Embedding documents (first run downloads ~420MB model)...
Indexed 5 documents

Q: What is Valkey used for?
  0.921 | Valkey is a high-performance in-memory data store.
  0.743 | Vector search finds semantically similar documents.

Q: How does Haystack work?
  0.918 | Haystack is an open-source LLM framework by deepset.
  0.761 | ValkeyDocumentStore integrates directly with Haystack pipelines.

Q: How do I do vector similarity search?
  0.934 | Vector search finds semantically similar documents.
  0.712 | Cosine similarity measures the angle between two embedding vectors.
```
