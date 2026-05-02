`betterdb-agent-cache` is a multi-tier exact-match cache for AI agent workloads backed by Valkey. It combines three cache tiers behind one connection:

- **LLM tier** — caches full LLM responses by exact match on model + messages + params
- **Tool tier** — caches tool/function call results by tool name and argument hash
- **Session tier** — key-value store for agent state with per-field TTL

Works on vanilla Valkey 7+, Amazon ElastiCache, Google Cloud Memorystore, and Amazon MemoryDB with no modules required.

## Prerequisites

- **Valkey 7+** (no modules needed)
- Python 3.11+

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

## Step 2: Install

```bash
pip install betterdb-agent-cache
```

For provider-specific adapters, install the relevant extra:

```bash
pip install "betterdb-agent-cache[openai]"       # OpenAI
pip install "betterdb-agent-cache[anthropic]"    # Anthropic
pip install "betterdb-agent-cache[langchain]"    # LangChain
pip install "betterdb-agent-cache[langgraph]"    # LangGraph
pip install "betterdb-agent-cache[llamaindex]"   # LlamaIndex
```

## Step 3: Create an AgentCache

```python
import asyncio
import valkey.asyncio as valkey_client
from betterdb_agent_cache import AgentCache, TierDefaults
from betterdb_agent_cache.types import AgentCacheOptions

async def main():
    client = valkey_client.Valkey(host="localhost", port=6379)

    cache = AgentCache(AgentCacheOptions(
        client=client,
        tier_defaults={
            "llm":     TierDefaults(ttl=3600),   # LLM responses: 1 hour
            "tool":    TierDefaults(ttl=300),     # Tool results: 5 minutes
            "session": TierDefaults(ttl=1800),    # Session state: 30 min (sliding)
        },
        # cost_table is optional — 1,900+ models covered by default
    ))
```

No `initialize()` call needed — all tiers use plain Valkey commands (SET, GET, HINCRBY) with no index creation.

## Step 4: LLM Tier

```python
params = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "What is Valkey?"}],
    "temperature": 0,
}

# Check for a cached response
llm_result = await cache.llm.check(params)

if llm_result.hit:
    print("LLM cache HIT:", llm_result.response)
else:
    print("LLM cache MISS → calling LLM...")
    response = await call_llm(params)  # your LLM call

    from betterdb_agent_cache.types import LlmStoreOptions
    await cache.llm.store(params, response, LlmStoreOptions(
        tokens={"input": 14, "output": 62},  # enables cost tracking
    ))
```

The cache key is a SHA-256 hash of the canonicalized params. `{"messages": [...], "model": "gpt-4o"}` and `{"model": "gpt-4o", "messages": [...]}` produce the same key.

## Step 5: Tool Tier

```python
tool_name = "get_weather"
tool_args = {"city": "Sofia", "units": "metric"}

tool_result = await cache.tool.check(tool_name, tool_args)

if tool_result.hit:
    print("Tool cache HIT:", tool_result.response)
else:
    print("Tool cache MISS → calling API...")
    import json
    data = await get_weather(tool_args)  # your tool call

    from betterdb_agent_cache.types import ToolStoreOptions
    await cache.tool.store(tool_name, tool_args, json.dumps(data), ToolStoreOptions(
        cost=0.001,  # API call cost in dollars, for tracking
    ))
```

Tool args are serialized with recursively sorted keys before hashing, so `{"city": "Sofia", "units": "metric"}` and `{"units": "metric", "city": "Sofia"}` hit the same cache entry.

## Step 6: Session Tier

```python
thread_id = "user-42-session-1"

# Store agent state fields
await cache.session.set(thread_id, "last_intent", "book_flight")
await cache.session.set(thread_id, "destination", "Sofia")
await cache.session.set(thread_id, "departure_date", "2026-06-01")

# Retrieve a field (also refreshes its TTL)
intent = await cache.session.get(thread_id, "last_intent")
# "book_flight"

# Get all fields for a thread
state = await cache.session.get_all(thread_id)
# {"last_intent": "book_flight", "destination": "Sofia", "departure_date": "2026-06-01"}
```

Each `get()` refreshes the TTL on that field (sliding window). The session stays alive as long as the agent is actively using it.

## Key Formats

All keys are prefixed with the `name` option (default: `betterdb_ac`):

| Tier | Key Pattern |
|------|-------------|
| LLM cache | `betterdb_ac:llm:{sha256hash}` |
| Tool cache | `betterdb_ac:tool:{toolName}:{sha256hash}` |
| Session field | `betterdb_ac:session:{threadId}:{field}` |
| Stats hash | `betterdb_ac:__stats` |

```python
cache = AgentCache(AgentCacheOptions(
    client=client,
    name="myapp_prod",  # all keys prefixed with 'myapp_prod:'
))
```

## Cleanup

```python
# Destroy all state for a thread
await cache.session.destroy_thread(thread_id)

# Invalidate all LLM cache entries for a model
await cache.llm.invalidate_by_model("gpt-4o-mini")

# Close the client when done
await cache.shutdown()
await client.aclose()
```
