## The Challenge

Single-prompt caching works well for stateless queries. But in multi-turn conversations, the same user message means different things depending on context:

```python
# "Tell me more" means nothing without context
# Conversation A: "What is Valkey?" → "Tell me more"  (about Valkey)
# Conversation B: "What is Python?" → "Tell me more"  (about Python)
#
# Solution: embed the FULL context, not just the last message
```

## Strategy: Context-Aware Cache Keys

Instead of embedding only the last user message, we embed a summary of the full conversation context. This way, "Tell me more" in a Valkey conversation matches other Valkey follow-ups, not Python follow-ups.

## Step 1: Create Index with TAG Filter for User/Session

```python
import redis
import numpy as np
import hashlib
import time
from openai import OpenAI

client = redis.Redis(host="localhost", port=6379)
openai_client = OpenAI()
EMBEDDING_DIM = 1536

# Index with TAG field for per-user cache isolation
try:
    client.execute_command(
        "FT.CREATE", "conv_cache_idx",
        "SCHEMA",
        "context_summary", "TAG",
        "response", "TAG",
        "user_id", "TAG",
        "turn_count", "NUMERIC",
        "embedding", "VECTOR", "HNSW", "6",
        "TYPE", "FLOAT32",
        "DIM", str(EMBEDDING_DIM),
        "DISTANCE_METRIC", "COSINE",
    )
except redis.ResponseError:
    pass
```

## Step 2: Build Context Summary

```python
def build_context_string(messages: list) -> str:
    """Build a cacheable context string from conversation messages."""
    # Use last 3 turns (6 messages: user+assistant pairs)
    recent = messages[-6:]
    parts = []
    for msg in recent:
        role = msg["role"]
        content = msg["content"][:200]  # Truncate long messages
        parts.append(f"{role}: {content}")
    return " | ".join(parts)

def get_embedding(text: str) -> bytes:
    response = openai_client.embeddings.create(
        model="text-embedding-3-small", input=text,
    )
    return np.array(response.data[0].embedding, dtype=np.float32).tobytes()
```

## Step 3: Context-Aware Cache Lookup

```python
def lookup_conversation_cache(messages: list, user_id: str, threshold: float = 0.12):
    """Search cache for similar conversation contexts, scoped to user."""
    context = build_context_string(messages)
    query_vec = get_embedding(context)

    # Hybrid search: filter by user_id TAG + KNN on context embedding
    results = client.execute_command(
        "FT.SEARCH", "conv_cache_idx",
        f"@user_id:{{{user_id}}}=>[KNN 1 @embedding $query_vec]",
        "PARAMS", "2", "query_vec", query_vec,
        "DIALECT", "2",
    )

    if results[0] > 0:
        fields = results[2]
        fd = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
        score = float(fd.get("__embedding_score", "999"))
        if score < threshold:
            return {"hit": True, "response": fd.get("response", ""), "score": score}

    return {"hit": False}

def store_conversation_cache(messages: list, response: str, user_id: str):
    """Cache a conversation context + response."""
    context = build_context_string(messages)
    embedding_bytes = get_embedding(context)
    key_hash = hashlib.md5(context.encode()).hexdigest()
    cache_key = f"conv_cache:{user_id}:{key_hash}"

    client.hset(cache_key, mapping={
        "context_summary": context,
        "response": response,
        "user_id": user_id,
        "turn_count": str(len(messages)),
        "embedding": embedding_bytes,
    })
    client.expire(cache_key, 1800)  # 30 min TTL for conversations
```

## Step 4: Full Conversation Flow with Caching

```python
def chat_with_cache(messages: list, user_id: str) -> dict:
    """Chat with LLM, using conversation-aware semantic cache."""
    start = time.time()

    # Check cache
    cache = lookup_conversation_cache(messages, user_id)
    if cache["hit"]:
        return {
            "response": cache["response"],
            "source": "cache",
            "score": cache["score"],
            "latency_ms": round((time.time() - start) * 1000, 1),
        }

    # Cache miss — call LLM
    llm = openai_client.chat.completions.create(
        model="gpt-4", messages=messages,
    )
    answer = llm.choices[0].message.content

    # Store in cache
    store_conversation_cache(messages, answer, user_id)

    return {
        "response": answer,
        "source": "llm",
        "latency_ms": round((time.time() - start) * 1000, 1),
    }

# Example multi-turn conversation
convo = [
    {"role": "user", "content": "What is Valkey?"},
    {"role": "assistant", "content": "Valkey is an open-source in-memory data store..."},
    {"role": "user", "content": "How does it handle vector search?"},
]

result = chat_with_cache(convo, user_id="user_123")
print(f"Source: {result['source']}, Latency: {result['latency_ms']}ms")
```

> **Why TAG filter?** `@user_id:{user_123}` ensures User A's cached conversations don't leak to User B. The hybrid query (TAG + KNN) runs as a single atomic operation — pre-filters by user, then finds the nearest conversation context.

## Cache Isolation Strategies

| Strategy | TAG Filter | Best For |
|----------|-----------|----------|
| Per-user | `@user_id:{user_123}` | Personalized assistants |
| Per-session | `@session_id:{sess_abc}` | Short-lived chats |
| Global (shared) | No filter (`*`) | FAQ bots, common queries |
| Per-model | `@model:{gpt-4}` | Multi-model deployments |
