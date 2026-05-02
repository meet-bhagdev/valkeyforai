The session tier is a per-thread key-value store for agent state. Designed for the patterns that come up in multi-step, multi-turn agents: storing user intent, intermediate reasoning, extracted entities, and tool call context between invocations.

## How It Works

Each session field is stored as an individual Valkey key:

```
betterdb_ac:session:{thread_id}:{field}
```

Individual keys allow **per-field TTL** — different fields can have different expiry times — and `get()` automatically refreshes the TTL on each read (sliding window). The trade-off is that `get_all()` and `destroy_thread()` require a SCAN + pipeline rather than a single `HGETALL` or `DEL`.

## Basic Operations

```python
import valkey.asyncio as valkey_client
from betterdb_agent_cache import AgentCache, TierDefaults
from betterdb_agent_cache.types import AgentCacheOptions

client = valkey_client.Valkey(host="localhost", port=6379)
cache = AgentCache(AgentCacheOptions(
    client=client,
    tier_defaults={"session": TierDefaults(ttl=1800)},  # 30 min sliding window
))

thread_id = "user-42-thread-001"

# Write state fields
await cache.session.set(thread_id, "intent", "book_flight")
await cache.session.set(thread_id, "destination", "Sofia")
await cache.session.set(thread_id, "departure", "2026-06-01")

# Read a field (also refreshes its TTL)
intent = await cache.session.get(thread_id, "intent")
# "book_flight"

# Returns None for fields that don't exist or have expired
missing = await cache.session.get(thread_id, "return_date")
# None
```

## Getting All Fields

```python
state = await cache.session.get_all(thread_id)
print(state)
# {"intent": "book_flight", "destination": "Sofia", "departure": "2026-06-01"}
```

`get_all()` uses SCAN to find all keys for the thread and fetches them in a pipeline. Designed for sessions with dozens of fields — not thousands.

## Refreshing TTLs

```python
# On each user interaction, refresh all session fields to keep the session alive
await cache.session.touch(thread_id)
```

`touch()` extends the TTL on every field for the thread. Call it at the start of each agent invocation to prevent partial expiry where some fields outlive others.

## Deleting State

```python
# Delete a single field
await cache.session.delete(thread_id, "departure")

# Destroy the entire thread
deleted = await cache.session.destroy_thread(thread_id)
print(f"Deleted {deleted} keys")
```

## Multi-Step Agent Example

A booking agent that accumulates state across multiple tool calls:

```python
import json

async def run_booking_agent(thread_id: str, user_message: str) -> dict:
    # Load existing state
    state = await cache.session.get_all(thread_id)

    # Extract intent
    if "book" in user_message and "flight" in user_message:
        await cache.session.set(thread_id, "intent", "book_flight")

    # Extract destination
    import re
    dest_match = re.search(r"to (\w+)", user_message, re.IGNORECASE)
    if dest_match:
        await cache.session.set(thread_id, "destination", dest_match.group(1))

    # Extract departure date
    date_match = re.search(r"on (\d{4}-\d{2}-\d{2})", user_message)
    if date_match:
        await cache.session.set(thread_id, "departure", date_match.group(1))

    # Refresh all TTLs so the session doesn't partially expire
    await cache.session.touch(thread_id)

    # Read current state
    current_state = await cache.session.get_all(thread_id)

    # Search for flights only when we have enough context
    if (current_state.get("destination") and current_state.get("departure")
            and not current_state.get("search_results")):
        args = {
            "destination": current_state["destination"],
            "date": current_state["departure"],
        }
        cached = await cache.tool.check("search_flights", args)
        if not cached.hit:
            flight_data = await search_flights(current_state)
            await cache.tool.store("search_flights", args, json.dumps(flight_data))
            await cache.session.set(thread_id, "search_results", json.dumps(flight_data))
        else:
            await cache.session.set(thread_id, "search_results", cached.response)

    return await cache.session.get_all(thread_id)
```

## Session State Patterns

| Pattern | Implementation |
|---------|---------------|
| User intent tracking | `set(thread, "intent", value)` on each turn |
| Entity accumulation | One field per entity: `set(thread, "city", "Sofia")` |
| Conversation stage | `set(thread, "stage", "collecting_dates")` |
| Intermediate results | Store JSON: `set(thread, "search_results", json.dumps(data))` |
| Error recovery | `set(thread, "last_failed_step", "payment")` |
| Session keepalive | `touch(thread)` at start of each invocation |

## Per-Field TTL Override

```python
# Short-lived field: search results that go stale quickly
await cache.session.set(thread_id, "flight_prices", json.dumps(prices), ttl=300)

# Long-lived field: user preferences that persist across sessions
await cache.session.set(thread_id, "preferred_seat", "aisle", ttl=86400 * 30)
```

The per-call `ttl` overrides `tier_defaults["session"].ttl` for that specific field.
