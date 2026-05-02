## The Problem

Cookbook 01 stored messages in a LIST. But in production you also need to know: _who_ is this session for? _How many tokens_ have been used? _Which model_? _When_ was the last activity? Storing this metadata alongside the conversation enables session management, billing, and debugging.

## Data Model: Two Keys Per Session

```python
# Messages - LIST (same as cookbook 01)
chat:sess_abc123          → ["{"role":"user",...}", ...]

# Metadata - HASH (new)
meta:sess_abc123          → {
    user_id:       "user_42",
    model:         "claude-3-haiku",
    created_at:    "1710000000.0",
    last_active:   "1710003600.0",
    message_count: "12",
    token_count:   "4850",
    title:         "Valkey performance questions"
}
```

**Why this matters:** Valkey Hashes are perfect for metadata - each field is independently readable and writable. `HINCRBY` atomically increments token counts without read-modify-write races. `HSET` updates individual fields without touching others.

## Pattern 1: Create a Session with Metadata

```python
import os
from dotenv import load_dotenv

load_dotenv()

import asyncio, json, time
from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def create_session(client, session_id, user_id, model="claude-3-haiku"):
    meta_key = f"meta:{session_id}"
    await client.hset(meta_key, {
        "user_id": user_id,
        "model": model,
        "created_at": str(time.time()),
        "last_active": str(time.time()),
        "message_count": "0",
        "token_count": "0",
    })
    # Both keys expire together
    await client.expire(meta_key, 86400)  # 24 hours
    await client.expire(f"chat:{session_id}", 86400)
```

## Pattern 2: Add Message with Token Tracking

```python
async def add_message(client, session_id, role, content, tokens_used=0):
    chat_key = f"chat:{session_id}"
    meta_key = f"meta:{session_id}"

    # Append message to conversation
    await client.rpush(chat_key, [json.dumps({"role": role, "content": content})])

    # Update metadata atomically
    await client.hincrby(meta_key, "message_count", 1)
    await client.hincrby(meta_key, "token_count", tokens_used)
    await client.hset(meta_key, {"last_active": str(time.time())})
```

## Pattern 3: Sliding Window - Keep Last N Messages

Long conversations eat context windows. Use `LTRIM` to keep only the most recent messages:

```python
async def add_message_windowed(client, session_id, role, content, max_messages=50):
    chat_key = f"chat:{session_id}"

    # Append
    await client.rpush(chat_key, [json.dumps({"role": role, "content": content})])

    # Trim to last N messages - O(1) for small trims
    await client.ltrim(chat_key, -max_messages, -1)
```

**Why LTRIM?** Unlike deleting and re-inserting, `LTRIM` removes elements from the head of the list in-place. Combined with `RPUSH`, it creates a fixed-size sliding window with zero overhead.

## Pattern 4: List Active Sessions for a User

```python
async def list_user_sessions(client, user_id):
    """Find all active sessions for a user using SCAN."""
    sessions = []
    cursor = "0"
    while True:
        cursor, keys = await client.scan(cursor, match="meta:*", count=100)
        for key in keys:
            uid = await client.hget(key, "user_id")
            if uid and uid.decode() == user_id:
                meta = await client.hgetall(key)
                sessions.append({
                    k.decode(): v.decode() for k, v in meta.items()
                })
        if cursor == 0:
            break
    return sessions
```

**Production tip:** For large-scale deployments, maintain a per-user session index with a SET: `SADD user_sessions:{user_id} {session_id}`. This avoids scanning all keys.

## Pattern 5: Get Session Summary

```python
async def get_session_info(client, session_id):
    meta = await client.hgetall(f"meta:{session_id}")
    msg_count = await client.llen(f"chat:{session_id}")
    ttl = await client.ttl(f"meta:{session_id}")

    return {
        "session_id": session_id,
        "metadata": {k.decode(): v.decode() for k, v in meta.items()},
        "messages_stored": msg_count,
        "expires_in_seconds": ttl,
    }
```

## Valkey Commands Reference

Operation| Command| Latency  
---|---|---  
Create session metadata| `HSET meta:{id} field1 val1 ...`| ~0.1ms  
Increment token count| `HINCRBY meta:{id} token_count 150`| ~0.1ms  
Update single field| `HSET meta:{id} last_active 1710...`| ~0.1ms  
Get all metadata| `HGETALL meta:{id}`| ~0.1ms  
Get one field| `HGET meta:{id} token_count`| ~0.1ms  
Trim conversation| `LTRIM chat:{id} -50 -1`| ~0.1ms  
Scan for sessions| `SCAN 0 MATCH meta:* COUNT 100`| ~1ms  
  
**Next up:** Messages are stored, sessions are tracked. But how do you find _relevant_ past conversations? In the next cookbook, we'll add semantic memory - vector search over conversation history using Valkey's FT.SEARCH.