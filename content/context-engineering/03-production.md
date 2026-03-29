## Short-term vs Long-term Memory

The memory layer is the foundation of context engineering at scale. Valkey supports both memory types through TTL management:

```python
import valkey
import json
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Short-term memory: active session context (low TTL)
def store_short_term(session_id: str, key: str, value: str, ttl: int = 1800):
    """Store session-scoped context that expires after inactivity."""
    client.hset(f"session:{session_id}", key, value)
    client.expire(f"session:{session_id}", ttl)

# Long-term memory: persists across sessions (no TTL or high TTL)
def store_long_term(user_id: str, key: str, value: str):
    """Store cross-session user knowledge that persists indefinitely."""
    client.hset(f"memory:{user_id}", key, value)
    # No EXPIRE — this persists

# Example
store_short_term("sess_100", "current_topic", "billing")
store_short_term("sess_100", "escalation_level", "0")
store_long_term("alice", "communication_style", "prefers concise answers")
store_long_term("alice", "timezone", "America/Los_Angeles")
```

| Memory Type | TTL | Valkey Key Pattern | Use Case |
|-------------|-----|-------------------|----------|
| Short-term (session) | 30 min | `session:{session_id}` | Current task state, tool outputs |
| Short-term (chat) | 30 min | `chat:{session_id}` | Conversation messages |
| Long-term (user) | None | `memory:{user_id}` | Preferences, past interactions |
| Long-term (summary) | 30 days | `summary:{user_id}:{date}` | Session summaries for future reference |

## Context Pruning

Not everything belongs in the context window. Prune aggressively:

```python
def prune_old_messages(session_id: str, max_messages: int = 20):
    """Keep only the most recent messages."""
    client.ltrim(f"chat:{session_id}", -max_messages, -1)

def summarize_and_store(user_id: str, session_id: str, summary: str):
    """After a session ends, store a summary for long-term recall."""
    date = time.strftime("%Y-%m-%d")
    client.hset(f"summary:{user_id}:{date}", mapping={
        "session_id": session_id,
        "summary": summary,
        "timestamp": str(time.time()),
    })
    client.expire(f"summary:{user_id}:{date}", 86400 * 30)  # 30 days

# Prune chat to last 20 messages
prune_old_messages("sess_100")

# Store session summary for future context
summarize_and_store("alice", "sess_100", 
    "User asked about billing. Resolved a refund request for order ORD-12345.")
```

> **Key insight from Ankur Goyal (Braintrust):** "Good context engineering caches well. Bad context engineering is both slow and expensive."

## Multi-User Context Isolation

In production, you must isolate context between users:

```python
def get_user_context(user_id: str, session_id: str) -> dict:
    """Get all context for a specific user, properly isolated."""
    return {
        "memory": client.hgetall(f"memory:{user_id}"),
        "session": client.hgetall(f"session:{session_id}"),
        "history": [
            json.loads(m) for m in 
            client.lrange(f"chat:{session_id}", -10, -1)
        ],
    }

# Alice's context is completely separate from Bob's
alice_ctx = get_user_context("alice", "sess_alice_001")
bob_ctx = get_user_context("bob", "sess_bob_001")
```

## Monitoring Context Quality

Track how your context engineering system performs:

```python
def record_context_metrics(session_id: str, metrics: dict):
    """Track context assembly metrics."""
    client.hset(f"metrics:context:{session_id}", mapping={
        "sources_used": str(metrics.get("sources_used", 0)),
        "total_tokens": str(metrics.get("total_tokens", 0)),
        "assembly_time_ms": str(metrics.get("assembly_time_ms", 0)),
        "pruned_messages": str(metrics.get("pruned_messages", 0)),
        "timestamp": str(time.time()),
    })
    client.expire(f"metrics:context:{session_id}", 86400 * 7)  # 7 days

# After assembling context
record_context_metrics("sess_100", {
    "sources_used": 4,
    "total_tokens": 2850,
    "assembly_time_ms": 3.2,
    "pruned_messages": 5,
})

# Aggregate metrics
def get_avg_assembly_time(pattern: str = "metrics:context:*") -> float:
    """Calculate average context assembly time."""
    keys = client.keys(pattern)
    times = []
    for key in keys[:100]:  # Sample last 100 sessions
        t = client.hget(key, "assembly_time_ms")
        if t:
            times.append(float(t))
    return sum(times) / len(times) if times else 0.0
```

## Data Structure Reference

| Context Type | Valkey Type | Key Pattern | TTL | Why This Structure |
|-------------|------------|-------------|-----|-------------------|
| Agent config | Hash | `agent:config:{id}` | None | Structured key-value pairs |
| Chat history | List | `chat:{session}` | 30 min | Ordered, appendable, trimmable |
| Session state | Hash | `session:{session}` | 30 min | Fast field-level access |
| Tool outputs | Hash | `tool:{session}:step_{n}` | 1 hour | Per-step structured data |
| User memory | Hash | `memory:{user_id}` | None | Persistent preferences |
| Session summaries | Hash | `summary:{user}:{date}` | 30 days | Compressed long-term recall |
| KB embeddings | Hash + Vector | `kb:doc:{id}` | None | Semantic search via FT.SEARCH |
| Context metrics | Hash | `metrics:context:{session}` | 7 days | Performance monitoring |

## Production Checklist

| Area | Recommendation |
|------|---------------|
| Memory types | Use short-term (TTL) + long-term (persistent) memory |
| Pruning | LTRIM chat to last 20-50 messages per session |
| Isolation | Key patterns must include user_id or session_id |
| Token budget | Count tokens before each LLM call, trim from oldest |
| Monitoring | Track sources_used, total_tokens, assembly_time_ms |
| Summarization | Summarize sessions on close for long-term recall |
| Eviction | Set `maxmemory-policy allkeys-lru` for graceful degradation |
| Freshness | Use EXPIRE to auto-clean stale context |

> **Reference:** Based on best practices from the [Redis context engineering blog](https://redis.io/blog/context-engineering-best-practices-for-an-emerging-discipline/), drawing on insights from Andrej Karpathy, Lance Martin (LangChain), and Salvatore Sanfilippo (Redis founder).
