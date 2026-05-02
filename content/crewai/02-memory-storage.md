## The MemoryRecord Model

Each memory is a structured record with content, scope, categories, importance, and an embedding vector:

```python
import os
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4

class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(default="")
    scope: str = Field(default="/")
    categories: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    embedding: list[float] | None = Field(default=None)
    source: str | None = Field(default=None)
    private: bool = Field(default=False)
```

## Step 1: Serialization

Convert `MemoryRecord` to/from Valkey JSON documents:

```python
import json

def serialize_record(record: MemoryRecord) -> dict:
    return {
        "id": record.id,
        "content": record.content,
        "scope": record.scope,
        "categories_str": ",".join(record.categories),
        "metadata_str": json.dumps(record.metadata),
        "importance": record.importance,
        "created_at": record.created_at.timestamp(),
        "last_accessed": record.last_accessed.timestamp(),
        "embedding": record.embedding,
        "source": record.source or "",
        "private": "true" if record.private else "false",
    }
```

## Step 2: Create the HNSW Index

```python
from glide import (
    ft, VectorField, VectorAlgorithm, VectorFieldAttributesHnsw,
    VectorType, DistanceMetricType, NumericField, TextField,
    FtCreateOptions, DataType,
)

INDEX_NAME = "memory_idx"
KEY_PREFIX = "memory:"
VECTOR_DIM = 1536  # Amazon Titan embeddings

async def ensure_index(client):
    # Check if index already exists
    existing = await ft.list(client)
    if INDEX_NAME.encode() in existing:
        return

    hnsw = VectorFieldAttributesHnsw(
        dimensions=VECTOR_DIM,
        distance_metric=DistanceMetricType.COSINE,
        type=VectorType.FLOAT32,
    )
    await ft.create(
        client, INDEX_NAME,
        schema=[
            TextField("$.scope", alias="scope"),
            TextField("$.categories_str", alias="categories_str"),
            NumericField("$.importance", alias="importance"),
            NumericField("$.created_at", alias="created_at"),
            VectorField("$.embedding", VectorAlgorithm.HNSW,
                        alias="embedding", attributes=hnsw),
        ],
        options=FtCreateOptions(data_type=DataType.JSON, prefixes=[KEY_PREFIX]),
    )
```

**Valkey Command:**

```bash
FT.CREATE memory_idx ON JSON PREFIX 1 "memory:"
  SCHEMA $.scope AS scope TAG
         $.categories_str AS categories_str TAG
         $.importance AS importance NUMERIC
         $.created_at AS created_at NUMERIC
         $.embedding AS embedding VECTOR HNSW 6
           TYPE FLOAT32 DIM 1536 DISTANCE_METRIC COSINE
```

## Step 3: Store a Memory

```python
from glide import glide_json

async def store(client, record: MemoryRecord, ttl: int = 3600):
    key = f"{KEY_PREFIX}{record.id}"
    doc = serialize_record(record)
    await glide_json.set(client, key, "$", json.dumps(doc))
    await client.expire(key, ttl)
```

**Valkey Commands:**

```python
JSON.SET memory:abc-123-def $ '{"id":"abc-123-def","content":"Always check for null...","embedding":[0.12,-0.45,...],...}'
EXPIRE memory:abc-123-def 3600
```

## Step 4: Recall by Semantic Similarity

```python
import struct

async def recall(client, query_embedding: list[float], limit: int = 5):
    # Pack embedding to bytes for FT.SEARCH
    vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)

    result = await ft.search(
        client, INDEX_NAME,
        f"(*)=>[KNN {limit} @embedding $vec AS score]",
        options=FtSearchOptions(params={"vec": vec_bytes}),
    )

    # Parse results - score is cosine distance, convert to similarity
    memories = []
    if result and len(result) >= 2 and result[1]:
        for key, fields in result[1].items():
            doc = json.loads(fields[b"$"])
            score = 1.0 - float(fields[b"score"])
            memories.append((doc, score))

    return sorted(memories, key=lambda x: x[1], reverse=True)
```

**Valkey Command:**

```bash
FT.SEARCH memory_idx
  "(*)==>[KNN 5 @embedding $vec AS score]"
  PARAMS 2 vec <binary_vector_6144_bytes>
  LIMIT 0 5
```

## Step 5: Filtered Search

```python
async def search(client, query_embedding, scope: str = None, categories: list = None, limit: int = 5):
    # Build filter expression
    filters = []
    if scope:
        escaped = scope.replace("/", "\\/")
        filters.append(f"@scope:{{{escaped}*}}")
    if categories:
        joined = "|".join(categories)
        filters.append(f"@categories_str:{{{joined}}}")

    filter_str = " ".join(filters) if filters else "*"
    query = f"({filter_str})=>[KNN {limit} @embedding $vec AS score]"

    vec_bytes = struct.pack(f"<{len(query_embedding)}f", *query_embedding)
    result = await ft.search(client, INDEX_NAME, query, options=FtSearchOptions(params={"vec": vec_bytes}))
    # ... parse results same as recall()
```

## Next Steps

The storage backend is complete. Next we wire it into CrewAI's `Memory` system and run real agents.

[Next: 03 Agent Memory in Action →](<03-agent-memory.html>)