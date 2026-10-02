## Memory Isolation

Mem0 supports three levels of memory isolation via TAG fields in Valkey:

Level| Parameter| Use Case  
---|---|---  
User| `user_id`| Per-user preferences across all sessions  
Agent| `agent_id`| Per-agent knowledge (e.g., support bot vs sales bot)  
Session| `run_id`| Per-conversation context (ephemeral)  
  
## Step 1: Setup

```python
import os
from dotenv import load_dotenv

load_dotenv()

from mem0 import Memory

config = {
    "vector_store": {
        "provider": "valkey",
        "config": {
            "valkey_url": "valkey://localhost:6379",
            "collection_name": "multi_user_app",
            "embedding_model_dims": 1536,
        }
    }
}
memory = Memory.from_config(config)
```

## Step 2: Per-User Memories

```python
# User Alice
memory.add(
    [{"role": "user", "content": "I prefer dark mode and Python."}],
    user_id="alice",
)

# User Bob
memory.add(
    [{"role": "user", "content": "I use TypeScript and like light mode."}],
    user_id="bob",
)

# Search for Alice - only gets Alice's memories
alice_results = memory.search("What are the user preferences?", user_id="alice")
print("Alice:", [r["memory"] for r in alice_results["results"]])
# Alice: ['Prefers dark mode and Python']

# Search for Bob - only gets Bob's memories
bob_results = memory.search("What are the user preferences?", user_id="bob")
print("Bob:", [r["memory"] for r in bob_results["results"]])
# Bob: ['Uses TypeScript and likes light mode']
```

**How isolation works:** In Valkey, each memory is stored as a Hash with a `user_id` TAG field. When you search with `user_id="alice"`, Mem0 adds a TAG filter `@user_id:{alice}` to the `FT.SEARCH` query - ensuring Bob's memories are never returned.

## Step 3: Per-Agent Memories

```python
# Support agent knowledge
memory.add(
    [{"role": "user", "content": "Our refund policy is 30 days for unused items."}],
    agent_id="support_bot",
)

# Sales agent knowledge
memory.add(
    [{"role": "user", "content": "Current promotion: 20% off all premium plans."}],
    agent_id="sales_bot",
)

# Each agent only sees its own knowledge
support_results = memory.search("What is the refund policy?", agent_id="support_bot")
sales_results = memory.search("Any promotions?", agent_id="sales_bot")
```

## Step 4: Combined User + Agent

```python
# Add a memory scoped to both user AND agent
memory.add(
    [{"role": "user", "content": "I had an issue with order #12345."}],
    user_id="alice",
    agent_id="support_bot",
)

# Search: finds Alice's support interactions only
results = memory.search(
    "Previous issues",
    user_id="alice",
    agent_id="support_bot",
)
```

## Valkey Data Model

```python
# Each memory is stored as a Valkey Hash at:
#   mem0:multi_user_app:{memory_id}
#
# Fields:
#   memory_id: TAG
#   user_id: TAG      ← enables per-user filtering
#   agent_id: TAG     ← enables per-agent filtering
#   run_id: TAG       ← enables per-session filtering
#   memory: TAG       ← the extracted memory text
#   embedding: VECTOR ← HNSW FLOAT32 COSINE
#   created_at: NUMERIC
#   updated_at: NUMERIC
```