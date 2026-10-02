[← All RAG Cookbooks](</cookbooks/rag-pipelines/>)

# Vector Search Deep Dive

HNSW vs FLAT indexes, hybrid search, metadata filtering, and performance optimization.

## HNSW vs FLAT Indexes

#### HNSW (Approximate)

  * ~0.5ms search latency
  * 95%+ recall accuracy
  * Best for large datasets (>10K vectors)
  * Higher memory overhead

#### FLAT (Exact)

  * Linear scan - O(n) complexity
  * 100% accuracy guaranteed
  * Best for small datasets (<10K vectors)
  * Lower memory overhead

```bash
# HNSW Index (recommended for production)
FT.CREATE idx:hnsw ON HASH PREFIX 1 "doc:"
  SCHEMA
    embedding VECTOR HNSW 6
      TYPE FLOAT32
      DIM 1536
      DISTANCE_METRIC COSINE
      M 16                  # Max connections per node
      EF_CONSTRUCTION 200   # Build-time accuracy

# FLAT Index (for small datasets or exact search)
FT.CREATE idx:flat ON HASH PREFIX 1 "doc:"
  SCHEMA
    embedding VECTOR FLAT 6
      TYPE FLOAT32
      DIM 1536
      DISTANCE_METRIC COSINE
```

## HNSW Parameters

Parameter| Default| Description  
---|---|---  
**M**|  16| Max connections per node. Higher = better recall, more memory  
**EF_CONSTRUCTION**|  200| Build quality. Higher = slower build, better recall  
**EF_RUNTIME**|  10| Search quality. Set at query time  
  
## Hybrid Search: Vectors + Keywords

Combine vector similarity with keyword matching for more precise results:

```bash
# Create index with text and vector fields
FT.CREATE idx:hybrid ON HASH PREFIX 1 "doc:"
  SCHEMA
    content TAG
    category TAG
    embedding VECTOR HNSW 6
      TYPE FLOAT32
      DIM 1536
      DISTANCE_METRIC COSINE

# Hybrid query: vector search + category filter
FT.SEARCH idx:hybrid
  "(@category:{technical})=>[KNN 5 @embedding $vec AS score]"
  PARAMS 2 vec [embedding_bytes]
  DIALECT 2

# Hybrid query: vector search + keyword filter
FT.SEARCH idx:hybrid
  "(@content:{python programming})=>[KNN 5 @embedding $vec AS score]"
  PARAMS 2 vec [embedding_bytes]
  DIALECT 2
```

## Metadata Filtering

```bash
# Index with multiple filter fields
FT.CREATE idx:docs ON HASH PREFIX 1 "doc:"
  SCHEMA
    content TAG
    category TAG
    author TAG
    date NUMERIC
    embedding VECTOR HNSW 6
      TYPE FLOAT32
      DIM 1536
      DISTANCE_METRIC COSINE

# Filter by category
FT.SEARCH idx:docs
  "(@category:{billing})=>[KNN 5 @embedding $vec AS score]"
  ...

# Filter by date range
FT.SEARCH idx:docs
  "(@date:[1704067200 1706745600])=>[KNN 5 @embedding $vec AS score]"
  ...

# Multiple filters
FT.SEARCH idx:docs
  "(@category:{support} @author:{john})=>[KNN 5 @embedding $vec AS score]"
  ...
```

## Python Implementation

```python
import os
from dotenv import load_dotenv

load_dotenv()

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
```

[← Semantic Caching](<02-semantic-caching.html>) [Next: Cache Invalidation →](<04-cache-invalidation.html>)
