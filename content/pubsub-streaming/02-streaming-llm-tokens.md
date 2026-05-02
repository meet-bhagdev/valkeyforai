## The Problem

When streaming from an LLM (OpenAI, Anthropic, etc.), tokens arrive one at a time. If you have multiple clients watching the same response, you need to fan out each token to all of them. Valkey Pub/Sub is perfect for this:

```python
# Architecture:
#   LLM API  ──▶  Your Server  ──▶  Valkey PUBLISH  ──▶  Client A
#                    (token)       channel: llm:{id}  ──▶  Client B
#                                                     ──▶  Client C
```

## Step 1: Token Publisher (Server Side)

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey
import json
import time
import uuid

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

def stream_llm_response(prompt: str, request_id: str = None):
    """Simulate an LLM streaming response, publishing each token."""
    request_id = request_id or str(uuid.uuid4())[:8]
    channel = f"llm:stream:{request_id}"

    # Notify clients that streaming has started
    client.publish(channel, json.dumps({
        "type": "start",
        "request_id": request_id,
        "model": "gpt-4",
        "timestamp": time.time(),
    }))

    # Simulate token-by-token streaming
    tokens = ["Valkey", " is", " an", " open", "-source",
              " in", "-memory", " data", " store", "."]

    for i, token in enumerate(tokens):
        # In production, this would come from the LLM API:
        # for chunk in openai.chat.completions.create(stream=True):
        #     token = chunk.choices[0].delta.content

        client.publish(channel, json.dumps({
            "type": "token",
            "content": token,
            "index": i,
            "timestamp": time.time(),
        }))
        time.sleep(0.05)  # Simulate token delay

    # Notify clients that streaming is complete
    client.publish(channel, json.dumps({
        "type": "end",
        "request_id": request_id,
        "total_tokens": len(tokens),
        "timestamp": time.time(),
    }))

    return request_id

# Usage
rid = stream_llm_response("What is Valkey?")
print(f"Streamed response: {rid}")
```

## Step 2: Token Subscriber (Client Side)

```python
import valkey
import json

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

def watch_stream(request_id: str):
    """Subscribe to an LLM response stream and reassemble tokens."""
    pubsub = client.pubsub()
    channel = f"llm:stream:{request_id}"
    pubsub.subscribe(channel)

    full_response = []

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        data = json.loads(message["data"])

        if data["type"] == "start":
            print(f"Stream started (model: {data['model']})")

        elif data["type"] == "token":
            token = data["content"]
            full_response.append(token)
            print(token, end="", flush=True)  # Print token-by-token

        elif data["type"] == "end":
            print(f"\n--- Complete ({data['total_tokens']} tokens) ---")
            break

    pubsub.unsubscribe(channel)
    return "".join(full_response)

# Run in another terminal:
# result = watch_stream("abc123")
# Output: Valkey is an open-source in-memory data store.
```

## Step 3: OpenAI Integration

Here's the real-world version with the OpenAI API:

```python
from openai import OpenAI

openai_client = OpenAI()

def stream_openai_to_valkey(prompt: str, request_id: str):
    """Stream from OpenAI API → Valkey Pub/Sub → all subscribers."""
    channel = f"llm:stream:{request_id}"

    client.publish(channel, json.dumps({"type": "start"}))

    stream = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    token_count = 0
    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            client.publish(channel, json.dumps({
                "type": "token",
                "content": content,
                "index": token_count,
            }))
            token_count += 1

    client.publish(channel, json.dumps({
        "type": "end",
        "total_tokens": token_count,
    }))
```

## Multi-Client Fan-Out

**What makes this work:** Every `PUBLISH` is delivered to ALL subscribers on that channel simultaneously. If 100 clients are watching the same LLM response, all 100 receive each token at the same time - with zero additional cost. This is pure O(N) fan-out handled entirely by Valkey.

Metric| Value  
---|---  
Publish latency (per token)| ~0.1ms  
Delivery to 1 subscriber| ~0.1ms  
Delivery to 100 subscribers| ~0.5ms  
Max subscribers per channel| Unlimited  
Message size limit| 512MB (practical: keep small)