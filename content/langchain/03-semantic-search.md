## Why Semantic Search?

"How do I reset my password?" and "I forgot my password, help!" mean the same thing. Exact-match caching misses this. `ValkeyStore` uses vector similarity to match by meaning:

  * **HNSW index** - approximate nearest neighbor search with 99%+ recall
  * **Microsecond latency** - vector search in Valkey is sub-millisecond
  * **Real-time updates** - new vectors are searchable immediately, no rebuild needed

## Step 1: Configure ValkeyStore

```python
import os
from dotenv import load_dotenv

load_dotenv()

from langgraph_checkpoint_aws import ValkeyStore
from langchain_aws import BedrockEmbeddings

# Amazon Titan embeddings - 1536 dimensions
embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",
    region_name="us-west-2",
)

# ValkeyStore with HNSW vector index
store = ValkeyStore.from_conn_string(
    "valkey://localhost:6379",
    index={
        "collection_name": "semantic_cache",
        "dims": 1536,
        "embed": embeddings,
        "fields": ["text"],
        "index_type": "hnsw",
        "distance_metric": "COSINE",
    },
    ttl={"default_ttl": 60.0},  # 60 minutes
)
store.setup()  # Creates the FT index
```

## Step 2: Store Documents

```python
# Store a document - embedding is generated automatically
store.put(
    ("help-desk", "passwords"),  # namespace
    "q1",                          # key
    {
        "text": "How do I reset my password?",
        "answer": "Go to portal.company.com, click Forgot Password...",
    },
)

store.put(
    ("help-desk", "vpn"),
    "q2",
    {
        "text": "How do I connect to the VPN?",
        "answer": "Download the VPN client from IT portal...",
    },
)
```

## Step 3: Search by Meaning

```python
# Search with a paraphrased query
results = store.search(
    ("help-desk",),  # namespace prefix
    query="I forgot my password, help!",
    limit=3,
)

for r in results:
    print(f"Score: {r.score:.3f} - {r.value['text']}")

# Output:
# Score: 0.943 - How do I reset my password?
# Score: 0.412 - How do I connect to the VPN?
```

**Valkey Commands Fired:**

```python
# Index creation (once)
FT.CREATE semantic_cache_idx ON JSON PREFIX 1 "store:semantic_cache:"
  SCHEMA $.text AS text TAG
         $.embedding AS embedding VECTOR HNSW 6
           TYPE FLOAT32 DIM 1536 DISTANCE_METRIC COSINE

# Store document
JSON.SET store:semantic_cache:help-desk:passwords:q1 $ '{...}'
EXPIRE store:semantic_cache:help-desk:passwords:q1 3600

# Vector search
FT.SEARCH semantic_cache_idx
  "(*)==>[KNN 3 @embedding $vec AS score]"
  PARAMS 2 vec <binary_vector>
  LIMIT 0 3
```

## Step 4: HNSW Tuning

Tune the index for your speed/accuracy tradeoff:

Parameter| Default| Higher =| Lower =  
---|---|---|---  
`hnsw_m`| 16| Better recall, more memory| Faster, less memory  
`hnsw_ef_construction`| 200| Better index quality| Faster build  
`hnsw_ef_runtime`| 10| Better search accuracy| Faster queries  

```python
# High-accuracy configuration
store = ValkeyStore.from_conn_string(
    "valkey://localhost:6379",
    index={
        "collection_name": "precise_search",
        "dims": 1536,
        "embed": embeddings,
        "fields": ["text"],
        "index_type": "hnsw",
        "hnsw_m": 32,
        "hnsw_ef_construction": 400,
        "hnsw_ef_runtime": 50,
    },
)
```

## Next Steps

Now you have all three components: `ValkeySaver` (checkpoints), `ValkeyCache` (exact caching), and `ValkeyStore` (semantic search). Time to wire them all together.

[Next: 04 Full Agent - All Three Components →](<04-full-agent.html>)