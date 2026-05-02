## What is Mem0?

[Mem0](<https://github.com/mem0ai/mem0>) ("mem-zero") is an open-source memory layer for AI applications (YC S24). It has a **dedicated Valkey connector** (`provider: "valkey"`) that uses the `valkey` Python client with native `FT.CREATE`/`FT.SEARCH` for vector-based memory storage and retrieval.

**Mem0 has a first-class Valkey integration** - not just Redis compatibility. The `valkey.py` connector in Mem0's source uses the native `valkey` Python package and supports HNSW/FLAT indexing with configurable parameters.

## Step 1: Install

```bash
uv pip install mem0ai python-dotenv
```

The `valkey` Python client is included as a core dependency - no separate install needed.

## Step 2: Start Valkey with Search Module

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9-alpine
```

## Step 3: Configure Mem0 with Valkey

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
            "collection_name": "mem0",
            "embedding_model_dims": 1536,
            "index_type": "hnsw",
        }
    }
}

memory = Memory.from_config(config)
print("Mem0 connected to Valkey!")
```

## Step 4: Add Memories

```python
# Add memories from a conversation
messages = [
    {"role": "user", "content": "I love Italian food, especially pasta carbonara."},
    {"role": "assistant", "content": "Great choice! Carbonara is a classic Roman dish."},
]
result = memory.add(messages, user_id="user_001")
print(f"Added: {result}")

# Add more context
messages2 = [
    {"role": "user", "content": "I'm allergic to shellfish and prefer spicy food."},
    {"role": "assistant", "content": "Noted! I'll keep that in mind for recommendations."},
]
memory.add(messages2, user_id="user_001")
```

## Step 5: Search Memories

```python
# Search for relevant memories
results = memory.search(
    query="What food does this user like?",
    user_id="user_001",
    limit=3,
)

for entry in results["results"]:
    print(f"Memory: {entry['memory']}")
    print(f"Score: {entry.get('score', 'N/A')}\n")

# Output:
# Memory: Loves Italian food, especially pasta carbonara
# Score: 0.87
# Memory: Allergic to shellfish, prefers spicy food
# Score: 0.62
```

## Step 6: Get All Memories for a User

```python
# Retrieve all memories for a user
all_memories = memory.get_all(user_id="user_001")
for m in all_memories["results"]:
    print(f"  - {m['memory']}")
```

## Step 7: Use Memories in a Chatbot

```python
from openai import OpenAI

openai_client = OpenAI()

def chat_with_memory(message: str, user_id: str) -> str:
    # 1. Retrieve relevant memories
    relevant = memory.search(query=message, user_id=user_id, limit=3)
    memories_str = "\n".join(
        f"- {entry['memory']}" for entry in relevant["results"]
    )

    # 2. Build prompt with memories
    system = f"You are a helpful AI. Use these memories about the user:\n{memories_str}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]

    # 3. Generate response
    response = openai_client.chat.completions.create(
        model="gpt-4", messages=messages,
    )
    answer = response.choices[0].message.content

    # 4. Save new memories from this conversation
    memory.add(
        [{"role": "user", "content": message},
         {"role": "assistant", "content": answer}],
        user_id=user_id,
    )
    return answer

# Usage
response = chat_with_memory("Recommend me a restaurant", "user_001")
print(response)
# Will recommend Italian restaurants, avoid shellfish, suggest spicy options!
```

## How It Works Under the Hood

Operation| Mem0 API| Valkey Command  
---|---|---  
Add memory| `memory.add(messages, user_id)`| `HSET mem0:collection:id ...`  
Search| `memory.search(query, user_id)`| `FT.SEARCH` with KNN + TAG filter  
Get all| `memory.get_all(user_id)`| `FT.SEARCH @user_id:{id} *`  
Index creation| Automatic on init| `FT.CREATE` with HNSW + TAG fields  
  
**Source:** [mem0/vector_stores/valkey.py](<https://github.com/mem0ai/mem0/blob/main/mem0/vector_stores/valkey.py>) - The official Valkey connector in the Mem0 repository.

[Next →02 - Multi-User Memory](<02-multi-user-memory.html>)