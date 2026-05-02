## Architecture

```python
User: "I forgot my password, help!"
        │
        ▼
   ┌─ ValkeyStore.search() ─── semantic cache lookup
   │   score ≥ 0.90 → ✅ return cached answer (1ms)
   │   score < 0.90 → ❌ continue to LLM
   │
   ├─ ChatBedrockConverse.invoke() ─── LLM call (3-5s)
   │
   ├─ ValkeyStore.put() ─── cache the response
   │
   └─ ValkeySaver ─── checkpoint conversation state
```

## Step 1: Shared Valkey Connection

```python
import os
from dotenv import load_dotenv

load_dotenv()

from valkey import Valkey
from langgraph_checkpoint_aws import ValkeySaver, ValkeyStore, ValkeyCache
from langchain_aws import ChatBedrockConverse, BedrockEmbeddings

# Single Valkey connection shared across all components
valkey_client = Valkey.from_url("valkey://localhost:6379", decode_responses=False)

# Embeddings for semantic search
embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",
    region_name="us-west-2",
)

# LLM
model = ChatBedrockConverse(
    model="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-west-2",
)
```

## Step 2: Initialize All Three Components

```python
# 1. Checkpointer - persists conversation state
saver = ValkeySaver(client=valkey_client, ttl=3600)

# 2. Semantic store - vector search for cache lookups
store = ValkeyStore(
    client=valkey_client,
    index={
        "collection_name": "helpdesk_cache",
        "dims": 1536,
        "embed": embeddings,
        "fields": ["query"],
        "index_type": "hnsw",
    },
    ttl={"default_ttl": 60.0},
)
store.setup()

# 3. Exact cache - fast key-value cache for repeated prompts
cache = ValkeyCache(client=valkey_client, prefix="llm_cache:", ttl=3600)
```

## Step 3: Build the Agent Graph

```python
from langgraph.graph import StateGraph, MessagesState
from langchain_core.messages import HumanMessage
import hashlib

SIMILARITY_THRESHOLD = 0.90

def helpdesk_agent(state: MessagesState):
    user_msg = state["messages"][-1].content

    # 1. Check semantic cache
    hits = store.search(("helpdesk",), query=user_msg, limit=1)
    if hits and hits[0].score >= SIMILARITY_THRESHOLD:
        cached_answer = hits[0].value["answer"]
        return {"messages": [AIMessage(content=cached_answer)]}

    # 2. Cache miss - call LLM
    response = model.invoke(state["messages"])

    # 3. Store in semantic cache for future hits
    key = hashlib.md5(user_msg.encode()).hexdigest()[:12]
    store.put(
        ("helpdesk",), key,
        {"query": user_msg, "answer": response.content},
    )

    return {"messages": [response]}

# Build and compile with ValkeySaver
builder = StateGraph(MessagesState)
builder.add_node("agent", helpdesk_agent)
builder.set_entry_point("agent")
builder.set_finish_point("agent")

graph = builder.compile(checkpointer=saver)
```

## Step 4: Run the Complete Flow

```python
import time

config = {"configurable": {"thread_id": "user-42"}}

# First question - cache miss, calls LLM
t0 = time.time()
r1 = graph.invoke(
    {"messages": [HumanMessage(content="How do I reset my password?")]},
    config,
)
print(f"❌ MISS: {(time.time()-t0)*1000:.0f}ms")

# Paraphrased question - cache hit!
t0 = time.time()
r2 = graph.invoke(
    {"messages": [HumanMessage(content="I forgot my password, help!")]},
    config,
)
print(f"✅ HIT:  {(time.time()-t0)*1000:.1f}ms")

# Output:
# ❌ MISS: 4200ms
# ✅ HIT:  3.1ms
```

**Complete Valkey Command Sequence (cache miss):**

```python
# 1. Semantic cache lookup
FT.SEARCH helpdesk_cache_idx "(*)==>[KNN 1 @embedding $vec]" ...

# 2. (No match - call LLM via Bedrock)

# 3. Store response in semantic cache
JSON.SET store:helpdesk_cache:helpdesk:a1b2c3d4e5f6 $ '{...}'
EXPIRE store:helpdesk_cache:helpdesk:a1b2c3d4e5f6 3600

# 4. Checkpoint conversation state
JSON.SET checkpoint:user-42:__empty__:cp_001 $ '{...}'
EXPIRE checkpoint:user-42:__empty__:cp_001 3600
```

## Next Steps

You now have a complete LangGraph agent with Valkey-backed checkpointing, semantic caching, and vector search. To deploy to production, see the [ElastiCache for Valkey Getting Started guide](<https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/WhatIs.html>) - just swap `valkey://localhost:6379` for `valkeys://your-cluster.amazonaws.com:6379`.

[← Back to LangChain Cookbooks](</cookbooks/langchain/>)