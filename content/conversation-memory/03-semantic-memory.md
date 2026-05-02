## The Problem

Cookbook 01-02 gave us ordered chat history. But what if a user asks "How do I deploy?" and three weeks ago they discussed deployment in a different session? `LRANGE` can't find that - it only reads the current session. You need **semantic search** : finding messages by meaning, not position.

## Architecture

```python
User asks: "How do I deploy?"
        │
        ▼
   Embed query → [0.12, -0.45, 0.78, ...]
        │
        ▼
   FT.SEARCH memory_idx "(*)==>[KNN 5 @embedding $vec]"
        │
        ▼
   Returns: messages about deployment from ANY session
```

## Prerequisites

  * Valkey with the **valkey-search** module (use `valkey/valkey-bundle` Docker image)
  * An embedding model (we use Amazon Bedrock Titan, but any works)

## Step 1: Start Valkey with Search Module

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9-alpine
```

The `valkey-bundle` image includes valkey-search for vector similarity search and valkey-json for JSON document storage.

## Step 2: Create the Vector Index

```python
import os
from dotenv import load_dotenv

load_dotenv()

from glide import (
    GlideClient, GlideClientConfiguration, NodeAddress,
    ft, TagField, NumericField,
    VectorField, VectorAlgorithm, VectorFieldAttributesHnsw,
    VectorType, DistanceMetricType,
    FtCreateOptions, DataType,
)

async def create_memory_index(client):
    # Check if index already exists
    existing = await ft.list(client)
    names = [n.decode() for n in existing]
    if "memory_idx" in names:
        return

    hnsw = VectorFieldAttributesHnsw(
        dimensions=1536,  # Titan embedding size
        distance_metric=DistanceMetricType.COSINE,
        type=VectorType.FLOAT32,
    )

    await ft.create(
        client, "memory_idx",
        schema=[
            TagField("$.session_id", alias="session_id"),
            TagField("$.role", alias="role"),
            TagField("$.user_id", alias="user_id"),
            NumericField("$.timestamp", alias="timestamp"),
            VectorField("$.embedding", VectorAlgorithm.HNSW,
                        alias="embedding", attributes=hnsw),
        ],
        options=FtCreateOptions(data_type=DataType.JSON, prefixes=["mem:"]),
    )
    print("✅ Index created")
```

**The key thing here:** `FT.CREATE ON JSON` indexes fields inside JSON documents. The HNSW algorithm provides approximate nearest-neighbor search with ~99% recall at sub-millisecond latency. Once created, the index automatically updates as you add/remove documents.

## Step 3: Store Messages with Embeddings

```python
import json, struct, time, uuid, boto3
from glide import glide_json

def get_embedding(text):
    """Get embedding from Bedrock Titan."""
    bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v1",
        body=json.dumps({"inputText": text}),
    )
    return json.loads(response["body"].read())["embedding"]


async def store_memory(client, session_id, user_id, role, content):
    """Store a message with its embedding for semantic search."""
    embedding = get_embedding(content)
    doc_id = f"mem:{uuid.uuid4().hex[:12]}"

    doc = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "timestamp": time.time(),
        "embedding": embedding,
    }

    await glide_json.set(client, doc_id, "$", json.dumps(doc))
    return doc_id
```

## Step 4: Search by Meaning

```python
async def search_memory(client, query, limit=5, user_id=None):
    """Find semantically similar messages across all sessions."""
    from glide import FtSearchOptions

    query_embedding = get_embedding(query)
    vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)

    # Build filter - optionally scope to a user
    filter_expr = "*"
    if user_id:
        filter_expr = f"@user_id:{{{user_id}}}"

    query_str = f"({filter_expr})==>[KNN {limit} @embedding $vec AS score]"

    result = await ft.search(
        client, "memory_idx", query_str,
        options=FtSearchOptions(params={"vec": vec_bytes}),
    )

    # Parse results
    memories = []
    if result and len(result) >= 2:
        for key, fields in result[1].items():
            doc = json.loads(fields[b"$"])
            score = 1.0 - float(fields.get(b"score", 1))
            memories.append({
                "content": doc["content"],
                "session_id": doc["session_id"],
                "role": doc["role"],
                "score": round(score, 3),
            })
    return memories
```

## Step 5: Put It Together

```python
async def demo():
    config = GlideClientConfiguration([NodeAddress("localhost", 6379)])
    client = await GlideClient.create(config)

    await create_memory_index(client)

    # Store memories from different sessions
    await store_memory(client, "sess_1", "alice", "user",
        "We deployed to ECS using a blue-green strategy")
    await store_memory(client, "sess_2", "alice", "assistant",
        "Valkey HNSW index provides sub-millisecond vector search")
    await store_memory(client, "sess_3", "alice", "user",
        "Our CI/CD pipeline runs on CodePipeline with canary deploys")

    # Search across all sessions
    results = await search_memory(client, "How do I deploy my service?")
    print("🔍 Results for 'How do I deploy my service?':")
    for r in results:
        print(f"   [{r['score']:.3f}] ({r['session_id']}) {r['content']}")

    # Output:
    # [0.847] (sess_1) We deployed to ECS using a blue-green strategy
    # [0.812] (sess_3) Our CI/CD pipeline runs on CodePipeline with canary deploys
    # [0.234] (sess_2) Valkey HNSW index provides sub-millisecond vector search
```

**Notice:** The query "How do I deploy?" matched messages about "blue-green strategy" and "CI/CD pipeline" - completely different words, but semantically related. This is the power of vector search. And it found them across different sessions.

## Valkey Commands Reference

Operation| Command| Latency  
---|---|---  
Create index| `FT.CREATE memory_idx ON JSON ...`| ~5ms (once)  
Store memory| `JSON.SET mem:{id} $ '{...}'`| ~0.2ms  
Semantic search| `FT.SEARCH memory_idx "(*)==>[KNN 5 ...]"`| ~1-3ms  
Delete memory| `DEL mem:{id}`| ~0.1ms  
List indexes| `FT._LIST`| ~0.1ms  
  
## Filtering: Scope + Semantic

Combine vector search with metadata filters in a single query:

```python
# Only search alice's messages
"(@user_id:{alice})==>[KNN 5 @embedding $vec AS score]"

# Only search assistant responses
"(@role:{assistant})==>[KNN 5 @embedding $vec AS score]"

# Only search a specific session
"(@session_id:{sess_1})==>[KNN 5 @embedding $vec AS score]"
```

Filters are applied _before_ the vector search, so they're fast - Valkey only computes distances for matching documents.

**Next up:** Semantic memory finds relevant past conversations. But what about avoiding redundant LLM calls? In the next cookbook, we'll build a semantic cache that returns cached responses when a similar question was already answered.