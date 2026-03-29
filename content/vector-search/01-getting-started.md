## Prerequisites

  * Valkey server with the **valkey-search** module loaded
  * Python 3.9+ with the `valkey` and `numpy` packages

## Step 1: Start Valkey with Search Module

```bash
# Start Valkey with the search module loaded
valkey-server --loadmodule /usr/lib/valkey/libsearch.so
```

Verify the module is loaded:

```bash
valkey-cli MODULE LIST
# Should show "search" in the output
```

## Step 2: Install Python Client

```bash
pip install valkey numpy
```

We use the standard `redis` Python client. Module commands like `FT.CREATE` are called via `execute_command()`.

## Step 3: Create a Vector Index

```python
import valkey
import numpy as np

client = valkey.Valkey(host="localhost", port=6379)

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
    print("Index created!")
except valkey.ResponseError as e:
    print(f"Index may already exist: {e}")
```

**Key parameters:** `HNSW` is the indexing algorithm (fast approximate search). `6` means 3 key-value pairs follow: TYPE, DIM, DISTANCE_METRIC. `COSINE` measures angle similarity (best for normalized embeddings).

## Step 4: Store Vectors

Vectors must be stored as binary FLOAT32 data. Use Python's `struct.pack` or NumPy's `.tobytes()`:

```python
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
```

## Step 5: Run a KNN Search

```python
# Query vector — find documents similar to this
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
```

**Expected output:**

```python
Found 3 results:

  doc:3 (score: 0.0012...)
    Vector search finds similar items fast

  doc:1 (score: 0.0045...)
    Valkey is a fast in-memory data store

  doc:4 (score: 0.32...)
    Neural networks power modern AI
```

## Step 6: Check Index Info

```python
# Get index metadata
info = client.execute_command("FT.INFO", "doc_index")
print(info)
```

## How It Works

Operation| Command| Notes  
---|---|---  
Create index| `FT.CREATE`| Defines fields and vector params  
Store vector| `HSET key field value`| Vectors as binary FLOAT32  
KNN search| `FT.SEARCH idx "*=>[KNN k @field $param]"`| Returns k nearest neighbors  
Index info| `FT.INFO idx`| Shows schema, doc count, etc.  
Drop index| `FT.DROPINDEX idx`| Removes index (not data)  
  
**Important:** Vectors MUST be binary FLOAT32 data, not strings. Always use `np.array(vec, dtype=np.float32).tobytes()` or `struct.pack(f'{len(vec)}f', *vec)` to serialize.

[Next →02 — Semantic Search with Embeddings](<02-semantic-search.html>)