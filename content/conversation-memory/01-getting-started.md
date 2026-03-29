## Why Valkey for Conversation Memory?

LLMs are stateless — every API call starts from scratch. Conversation memory bridges the gap. Valkey is ideal because:

  * **Sub-millisecond reads** — `LRANGE` returns the last 50 messages in ~0.1ms
  * **Atomic appends** — `RPUSH` adds messages without race conditions
  * **Built-in TTL** — Sessions auto-expire with `EXPIRE`, no cleanup jobs needed
  * **GLIDE client** — Official Valkey client with Rust core for high performance

## Prerequisites

  * Docker installed (or a running Valkey instance)
  * Python 3.9+

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

Verify it's running:

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install GLIDE

```bash
pip install valkey-glide
```

GLIDE is the official Valkey client — Rust core with Python bindings. It works with both standalone Valkey and ElastiCache for Valkey clusters.

## Step 3: Understand the Data Model

Each conversation is stored as a **Valkey List** :

```python
# Key format: chat:{session_id}
# Each element is a JSON-encoded message

chat:sess_abc123 → [
    '{"role": "user", "content": "What is Valkey?"}',
    '{"role": "assistant", "content": "Valkey is an open-source..."}',
    '{"role": "user", "content": "How fast is it?"}',
    '{"role": "assistant", "content": "Sub-millisecond latency..."}'
]
```

**Key Insight:** Valkey Lists are doubly-linked lists optimized for push/pop at both ends. `RPUSH` appends in O(1). `LRANGE -N -1` retrieves the last N messages in O(N). This maps perfectly to conversation history — always appending, always reading the tail.

## Step 4: Connect and Store Messages

```python
import asyncio
import json
from glide import GlideClient, GlideClientConfiguration, NodeAddress


async def main():
    # Connect to Valkey with GLIDE
    config = GlideClientConfiguration([NodeAddress("localhost", 6379)])
    client = await GlideClient.create(config)

    session_id = "sess_abc123"
    key = f"chat:{session_id}"

    # Store a conversation
    messages = [
        {"role": "user", "content": "What is Valkey?"},
        {"role": "assistant", "content": "Valkey is an open-source, high-performance key-value store."},
        {"role": "user", "content": "How fast is it?"},
        {"role": "assistant", "content": "Sub-millisecond latency for most operations."},
    ]

    for msg in messages:
        await client.rpush(key, [json.dumps(msg)])

    # Set TTL — session expires after 1 hour
    await client.expire(key, 3600)

    print("✅ Conversation stored")


asyncio.run(main())
```

## Step 5: Retrieve Conversation History

```python
async def get_history(client, session_id, last_n=50):
    """Retrieve the last N messages from a conversation."""
    key = f"chat:{session_id}"

    # LRANGE with negative indices = last N messages
    raw = await client.lrange(key, -last_n, -1)

    return [json.loads(msg) for msg in raw]


# Usage
history = await get_history(client, "sess_abc123")
for msg in history:
    print(f"{msg['role']}: {msg['content']}")

# user: What is Valkey?
# assistant: Valkey is an open-source, high-performance key-value store.
# user: How fast is it?
# assistant: Sub-millisecond latency for most operations.
```

## Step 6: Feed History to an LLM

The conversation history is already in the format LLMs expect — a list of `{"role", "content"}` dicts:

```python
import boto3, json

async def chat(client, session_id, user_message):
    # 1. Save the user message
    key = f"chat:{session_id}"
    await client.rpush(key, [json.dumps({"role": "user", "content": user_message})])

    # 2. Get conversation history (last 20 messages)
    history = await get_history(client, session_id, last_n=20)

    # 3. Call the LLM with full context
    bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 500,
            "messages": history,  # ← directly from Valkey
        }),
    )
    assistant_msg = json.loads(response["body"].read())["content"][0]["text"]

    # 4. Save the assistant response
    await client.rpush(key, [json.dumps({"role": "assistant", "content": assistant_msg})])

    # 5. Refresh TTL
    await client.expire(key, 3600)

    return assistant_msg
```

## How It Works Under the Hood

Operation| Valkey Command| Latency  
---|---|---  
Append message| `RPUSH chat:{id} '{"role":"user",...}'`| ~0.1ms  
Get last 20 messages| `LRANGE chat:{id} -20 -1`| ~0.1ms  
Set session TTL| `EXPIRE chat:{id} 3600`| ~0.1ms  
Check TTL remaining| `TTL chat:{id}`| ~0.1ms  
Get conversation length| `LLEN chat:{id}`| ~0.1ms  
Delete conversation| `DEL chat:{id}`| ~0.1ms  
  
## ElastiCache for Valkey

To use ElastiCache instead of local Docker, just change the connection:

```python
# Local Docker
config = GlideClientConfiguration([NodeAddress("localhost", 6379)])

# ElastiCache for Valkey
config = GlideClientConfiguration(
    [NodeAddress("my-cluster.xxxxx.cache.amazonaws.com", 6379)],
    use_tls=True,
)
```

Everything else stays the same. GLIDE handles the connection, TLS, and cluster topology automatically.

**What's Next:** In the next cookbook, we'll add session metadata — tracking user IDs, token counts, and model info alongside the conversation history using Valkey Hashes.

[ Next → 02 — Session Management ](<02-session-management.html>)

