## What is Context Engineering?

Context engineering is the discipline of **systematically selecting, structuring, and delivering the right context** to an LLM to improve reliability and performance.

As Andrej Karpathy (OpenAI founding team) puts it: *"Context engineering is the delicate art and science of filling the context window with just the right information for the next step."*

It goes beyond prompt engineering. Prompts are just one input. Context engineering treats context as **infrastructure** - including retrieved knowledge, long-term memory, tool calls, conversation history, and structured formatting.

> **Why this matters for production AI:** Most agent failures are not model failures - they are context failures. The right context, delivered at the right time, is the difference between a useful agent and one that hallucinates.

## The 5 Context Sources

Every LLM call needs context assembled from up to 5 sources. Valkey can serve as the unified backend for all of them:

| Source | What It Is | Valkey Data Structure | Example |
|--------|-----------|----------------------|---------|
| **System Instructions** | Agent role, constraints, output format | `HSET` (hash) | `agent:config:support_bot` |
| **Conversation History** | Recent messages in the current session | `RPUSH` / `LRANGE` (list) | `chat:session:abc123` |
| **Retrieved Knowledge** | Relevant docs/facts from a knowledge base | `FT.SEARCH` KNN (vector) | Semantic search over embeddings |
| **Tool Outputs** | Results from function/API calls | `HSET` (hash) | `tool:result:step_3` |
| **Long-term Memory** | User preferences, past interactions | `HSET` with no TTL | `memory:user:alice` |

## Prerequisites

- Valkey with the **valkey-search** module (or ElastiCache for Valkey 8.2+)
- Python 3.12+ with `valkey`

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9-alpine
```

## Step 2: Install Dependencies

```bash
uv pip install valkey python-dotenv
```

## Step 3: Store System Instructions

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey
import json

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Store agent configuration
client.hset("agent:config:support_bot", mapping={
    "role": "You are a helpful customer support agent for Acme Corp.",
    "constraints": "Always be polite. Never share internal pricing. Escalate billing issues.",
    "output_format": "Respond in markdown. Keep answers under 200 words.",
    "tools_available": json.dumps(["search_kb", "check_order", "create_ticket"]),
})
print("System instructions stored")
```

## Step 4: Manage Conversation History

```python
import time

def add_message(session_id: str, role: str, content: str):
    """Append a message to the conversation history."""
    msg = json.dumps({"role": role, "content": content, "ts": time.time()})
    client.rpush(f"chat:{session_id}", msg)
    # Keep only last 50 messages (sliding window)
    client.ltrim(f"chat:{session_id}", -50, -1)
    # Set TTL for session cleanup (30 min inactivity)
    client.expire(f"chat:{session_id}", 1800)

def get_history(session_id: str, last_n: int = 10) -> list:
    """Retrieve recent conversation history."""
    raw = client.lrange(f"chat:{session_id}", -last_n, -1)
    return [json.loads(m) for m in raw]

# Example conversation
add_message("sess_001", "user", "What's your refund policy?")
add_message("sess_001", "assistant", "Our refund policy allows returns within 30 days...")
add_message("sess_001", "user", "Can I return an opened item?")

history = get_history("sess_001")
for msg in history:
    print(f"  {msg['role']}: {msg['content'][:60]}...")
```

## Step 5: Store Tool Outputs

```python
def store_tool_output(session_id: str, step: int, tool_name: str, result: dict):
    """Store the output of a tool call for context assembly."""
    key = f"tool:{session_id}:step_{step}"
    client.hset(key, mapping={
        "tool": tool_name,
        "result": json.dumps(result),
        "timestamp": str(time.time()),
    })
    client.expire(key, 3600)  # 1 hour TTL

def get_tool_outputs(session_id: str) -> list:
    """Retrieve all tool outputs for this session."""
    keys = client.keys(f"tool:{session_id}:step_*")
    outputs = []
    for key in sorted(keys):
        data = client.hgetall(key)
        outputs.append({
            "tool": data["tool"],
            "result": json.loads(data["result"]),
        })
    return outputs

# Example: agent called the order lookup tool
store_tool_output("sess_001", 1, "check_order", {
    "order_id": "ORD-12345",
    "status": "delivered",
    "date": "2025-03-15",
})
```

## Step 6: Long-term User Memory

```python
def remember(user_id: str, key: str, value: str):
    """Store a long-term memory about a user."""
    client.hset(f"memory:{user_id}", key, value)
    # No TTL - persists across sessions

def recall(user_id: str) -> dict:
    """Retrieve all memories about a user."""
    return client.hgetall(f"memory:{user_id}")

# Store user preferences
remember("alice", "preferred_language", "English")
remember("alice", "tier", "premium")
remember("alice", "last_issue", "billing dispute on ORD-12345")

memories = recall("alice")
print(f"Alice's memories: {memories}")
```

## The Pyramid Approach

Structure your context from general to specific - background first, then narrowing to the task:

```python
# Layer 1: System instructions (broadest)
# Layer 2: User memory (preferences, history)
# Layer 3: Retrieved knowledge (relevant docs)
# Layer 4: Conversation history (recent context)
# Layer 5: Current message + tool outputs (most specific)
```

> **Reference:** This approach is described in the [Redis context engineering blog](https://redis.io/blog/context-engineering-best-practices-for-an-emerging-discipline/) and draws on guidance from Andrej Karpathy, Tobi Lutke (Shopify CEO), and Philipp Schmid (Google DeepMind).
