## What is Pub/Sub?

Valkey Pub/Sub is a fire-and-forget messaging system. Publishers send messages to **channels** , and any number of subscribers listening on that channel receive them instantly. It's perfect for:

  * **Streaming LLM tokens** to multiple clients simultaneously
  * **AI agent events** - broadcasting tool completions and state changes
  * **Real-time notifications** - alerting dashboards of new predictions

**Pub/Sub vs Streams:** Pub/Sub is ephemeral - if no one is listening, messages are lost. Valkey Streams (Cookbook 03) are durable - messages persist and can be replayed. Use Pub/Sub for live broadcasting, Streams for guaranteed delivery.

## Prerequisites

  * Docker installed (or a running Valkey instance)
  * Python 3.12+

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9-alpine
```

## Step 2: Install Dependencies

```bash
uv pip install valkey python-dotenv
```

## Step 3: Create a Publisher

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey
import time
import json

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

def publish_message(channel: str, message: dict):
    """Publish a JSON message to a channel."""
    payload = json.dumps(message)
    num_subscribers = client.publish(channel, payload)
    print(f"Published to {channel} → {num_subscribers} subscriber(s)")
    return num_subscribers

# Publish some messages
publish_message("ai:events", {
    "type": "prediction",
    "model": "gpt-4",
    "result": "positive",
    "confidence": 0.95,
    "timestamp": time.time(),
})
# Published to ai:events → 0 subscriber(s)  (no one listening yet)
```

## Step 4: Create a Subscriber

Run this in a **separate terminal** - subscribers block while waiting for messages:

```python
import valkey
import json

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Create a Pub/Sub object
pubsub = client.pubsub()

# Subscribe to the channel
pubsub.subscribe("ai:events")
print("Subscribed to ai:events - waiting for messages...")

# Listen for messages (blocks)
for message in pubsub.listen():
    if message["type"] == "message":
        data = json.loads(message["data"])
        print(f"Received: {data}")

# Output when publisher sends a message:
# Received: {'type': 'prediction', 'model': 'gpt-4', 'result': 'positive', ...}
```

## Step 5: Pattern Subscriptions

Subscribe to multiple channels using glob patterns:

```python
# Subscribe to ALL ai:* channels at once
pubsub.psubscribe("ai:*")

# This matches:
#   ai:events
#   ai:predictions
#   ai:agent:tool_calls
#   ai:llm:tokens

for message in pubsub.listen():
    if message["type"] == "pmessage":
        channel = message["channel"]
        data = json.loads(message["data"])
        print(f"[{channel}] {data}")
```

## Step 6: Non-Blocking Subscriber

For applications that need to do other work while listening:

```python
import threading

def message_handler(message):
    """Called for each message received."""
    if message["type"] == "message":
        data = json.loads(message["data"])
        print(f"Handler: {data}")

# Subscribe with a callback (non-blocking)
pubsub.subscribe(**{"ai:events": message_handler})

# Run in background thread
thread = pubsub.run_in_thread(sleep_time=0.01)
print("Subscriber running in background")

# Do other work...
time.sleep(10)

# Stop when done
thread.stop()
```

## How It Works

Operation| Valkey Command| Latency  
---|---|---  
Publish message| `PUBLISH channel message`| ~0.1ms  
Subscribe to channel| `SUBSCRIBE channel`| ~0.1ms  
Pattern subscribe| `PSUBSCRIBE pattern`| ~0.1ms  
Unsubscribe| `UNSUBSCRIBE channel`| ~0.1ms  
Check active channels| `PUBSUB CHANNELS`| ~0.1ms  
Count subscribers| `PUBSUB NUMSUB channel`| ~0.1ms  
  
**Next up:** In the next cookbook, we'll use Pub/Sub to stream LLM tokens in real-time - broadcasting each token as it arrives from the model to multiple connected clients.

[ Next → 02 - Streaming LLM Tokens ](<02-streaming-llm-tokens.html>)