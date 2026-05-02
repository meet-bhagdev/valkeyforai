## The Problem

AI agents run multi-step workflows: plan → search → analyze → respond. If the process crashes at step 3, you lose everything and start over. Worse, if the agent calls the same expensive tool twice, you pay double. You need:

  * **Checkpointing** - save state after each step, resume on failure
  * **Tool result caching** - don't call the same API twice
  * **Activity log** - ordered record of what happened and when

## Three Valkey Patterns, One Agent

```python
┌─────────────────────────────────────────────────────────┐
│                    Valkey Server                        │
│                                                         │
│  HASH  agent:state:{run_id}  → Checkpoint (current step,│
│                                 intermediate results)   │
│                                                         │
│  STRING tool:cache:{hash}    → Cached tool outputs      │
│         (with TTL)              (avoid duplicate calls)  │
│                                                         │
│  STREAM agent:log:{run_id}   → Ordered event log        │
│                                 (replay & debugging)     │
└─────────────────────────────────────────────────────────┘
```

## Pattern 1: Agent Checkpointing with HASH

Save the agent's state after each step. If it crashes, resume from the last checkpoint.

```python
import os
from dotenv import load_dotenv

load_dotenv()

import json
from glide import GlideClient, GlideClientConfiguration, NodeAddress

async def save_checkpoint(client, run_id, step, data):
    """Save agent state after completing a step."""
    key = f"agent:state:{run_id}"
    await client.hset(key, {
        "current_step": str(step),
        "status": "in_progress",
        f"result_step_{step}": json.dumps(data),
        "updated_at": str(time.time()),
    })
    await client.expire(key, 86400)  # 24h TTL


async def load_checkpoint(client, run_id):
    """Load the last checkpoint to resume."""
    key = f"agent:state:{run_id}"
    state = await client.hgetall(key)
    if not state:
        return None
    return {k.decode(): v.decode() for k, v in state.items()}


async def mark_complete(client, run_id):
    await client.hset(f"agent:state:{run_id}", {"status": "complete"})
```

## Pattern 2: Tool Result Caching with STRING

Cache expensive tool outputs (API calls, web searches, database queries) so the agent doesn't repeat them.

```python
import hashlib

async def cached_tool_call(client, tool_name, args, tool_fn, ttl=300):
    """Call a tool, caching the result in Valkey."""
    # Create a cache key from tool name + arguments
    args_hash = hashlib.md5(json.dumps(args, sort_keys=True).encode()).hexdigest()[:12]
    cache_key = f"tool:cache:{tool_name}:{args_hash}"

    # Check cache first
    cached = await client.get(cache_key)
    if cached:
        print(f"⚡ Tool cache HIT: {tool_name}")
        return json.loads(cached)

    # Cache miss - call the tool
    print(f"🔄 Tool cache MISS: {tool_name} - calling...")
    result = tool_fn(**args)

    # Store with TTL
    await client.set(cache_key, json.dumps(result))
    await client.expire(cache_key, ttl)

    return result


# Usage
result = await cached_tool_call(
    client, "web_search",
    {"query": "Valkey vector search benchmarks"},
    tool_fn=web_search,
    ttl=600,  # cache for 10 minutes
)
```

**Worth knowing:** `SET key value EX ttl` is the simplest caching pattern in Valkey. For tool results, the TTL should match how quickly the data goes stale - 5 minutes for web searches, 1 hour for database queries, 24 hours for static lookups.

## Pattern 3: Activity Log with STREAM

Log every agent action to a Valkey Stream. This creates an ordered, persistent audit trail for debugging and replay.

```python
async def log_action(client, run_id, action, details):
    """Append an action to the agent's activity log."""
    stream_key = f"agent:log:{run_id}"
    await client.xadd(stream_key, [
        ("action", action),
        ("details", json.dumps(details)),
        ("ts", str(time.time())),
    ])


async def get_action_log(client, run_id):
    """Read the full activity log for a run."""
    from glide import StreamReadOptions
    stream_key = f"agent:log:{run_id}"
    result = await client.xread({stream_key: "0"}, StreamReadOptions(count=1000))
    if not result:
        return []

    entries = []
    for key, events in result.items():
        for entry_id, fields in events.items():
            entry = {k.decode(): v.decode() for k, v in fields}
            entry["id"] = entry_id.decode()
            entries.append(entry)
    return entries
```

## Putting It All Together: A Resumable Agent

```python
async def run_agent(client, run_id, query):
    # Check for existing checkpoint
    checkpoint = await load_checkpoint(client, run_id)
    start_step = int(checkpoint["current_step"]) + 1 if checkpoint else 1

    if start_step > 1:
        print(f"♻️  Resuming from step {start_step}")

    # Step 1: Search
    if start_step <= 1:
        await log_action(client, run_id, "search", {"query": query})
        results = await cached_tool_call(
            client, "web_search", {"query": query}, web_search)
        await save_checkpoint(client, run_id, 1, {"search_results": results})

    # Step 2: Analyze
    if start_step <= 2:
        await log_action(client, run_id, "analyze", {"input": "search results"})
        analysis = call_llm(f"Analyze: {results}")
        await save_checkpoint(client, run_id, 2, {"analysis": analysis})

    # Step 3: Respond
    if start_step <= 3:
        await log_action(client, run_id, "respond", {"status": "generating"})
        response = call_llm(f"Respond based on: {analysis}")
        await save_checkpoint(client, run_id, 3, {"response": response})

    await mark_complete(client, run_id)
    await log_action(client, run_id, "complete", {"status": "done"})
    return response
```

## Debugging: Inspect the Activity Log

```python
log = await get_action_log(client, "run_001")
for entry in log:
    print(f"  [{entry['id']}] {entry['action']}: {entry['details']}")

# Output:
# [1710000000001-0] search: {"query": "Valkey benchmarks"}
# [1710000000002-0] analyze: {"input": "search results"}
# [1710000000003-0] respond: {"status": "generating"}
# [1710000000004-0] complete: {"status": "done"}
```

## Valkey Commands Reference

Pattern| Command| Latency  
---|---|---  
Save checkpoint| `HSET agent:state:{id} step 2 result '{...}'`| ~0.1ms  
Load checkpoint| `HGETALL agent:state:{id}`| ~0.1ms  
Cache tool result| `SET tool:cache:{hash} '{...}' EX 300`| ~0.1ms  
Check tool cache| `GET tool:cache:{hash}`| ~0.1ms  
Log action| `XADD agent:log:{id} * action "search" ...`| ~0.1ms  
Read full log| `XREAD STREAMS agent:log:{id} 0`| ~0.1ms  
  
## Summary: Five Valkey Data Structures, One Conversation System

Across these 5 cookbooks, we've used every major Valkey data structure for a different aspect of conversation memory:

Cookbook| Data Structure| Purpose  
---|---|---  
01 Getting Started| `LIST`| Ordered chat history  
02 Session Management| `HASH`| Session metadata  
03 Semantic Memory| `JSON` \+ `FT.SEARCH`| Vector search over conversations  
04 Semantic Caching| `JSON` \+ `FT.SEARCH`| Cache LLM responses by meaning  
05 Agent State| `HASH` \+ `STRING` \+ `STREAM`| Checkpoints, tool cache, event log  
  
**One Valkey instance. Six data structures. Complete AI memory infrastructure.**