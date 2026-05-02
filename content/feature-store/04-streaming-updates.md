## The Architecture

Instead of writing features directly to Hashes, publish them to a Valkey Stream. A consumer reads the stream and writes to the online store. This decouples producers from consumers and enables:

  * **Fan-in** - Multiple services publish to one stream
  * **Replay** - Re-process historical updates if needed
  * **Backpressure** - Stream `MAXLEN` prevents unbounded growth
  * **Distributed processing** - Consumer groups for parallel workers

```python
# Architecture:
#   Service A  ──┐
#   Service B  ──┼──▶  Valkey Stream  ──▶  Consumer  ──▶  Valkey Hash
#   Service C  ──┘     (XADD)              (XREAD)        (HSET)
#
# Stream key: fs:stream:{feature_view_name}
# Message:    {entity_id, features (JSON), timestamp}
```

## Step 1: Publish Feature Updates

Any service can publish feature updates using `XADD`:

### Raw Valkey

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey
import json
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Publish a feature update to the stream
stream_key = "fs:stream:user_profile"
message = {
    "entity_id": "user_001",
    "features": json.dumps({"age": 28, "segment": "premium"}),
    "timestamp": str(time.time()),
    "feature_view": "user_profile",
}

# XADD with MAXLEN to cap stream size
entry_id = client.xadd(stream_key, message, maxlen=10000)
print(f"Published: {entry_id}")
# Published: 1710000000000-0
```

### With the Library

```python
from src import ValkeyFeatureStore, Entity, FeatureView, Feature, FeatureType

store = ValkeyFeatureStore(host="localhost", port=6379)

user = Entity(name="user", join_keys=["user_id"])
user_features = FeatureView(
    name="user_profile",
    entity=user,
    features=[
        Feature("age", FeatureType.INT),
        Feature("segment", FeatureType.STRING),
    ],
    ttl=3600,
)
store.register(user_features)

# Publish via streaming (uses XADD internally)
entry_id = store.streaming.publish(
    user_features,
    "user_001",
    {"age": 28, "segment": "premium"},
    maxlen=10000,
)
print(f"Published: {entry_id}")
```

## Step 2: Consume and Materialize

A consumer reads the stream and writes features to the online store Hash:

### Raw Valkey

```python
def consume_features(stream_key: str, last_id: str = "0-0"):
    """Read stream entries and write to online store."""
    entries = client.xread({stream_key: last_id}, count=100, block=1000)

    if not entries:
        return last_id

    new_last_id = last_id
    for stream, messages in entries:
        for msg_id, data in messages:
            entity_id = data["entity_id"]
            features = json.loads(data["features"])
            timestamp = float(data["timestamp"])
            view_name = data["feature_view"]

            # Write to online store Hash
            feature_key = f"fs:v1:{view_name}:{entity_id}"
            serialized = {k: str(v) for k, v in features.items()}
            serialized["_updated_at"] = str(timestamp)
            serialized["_feature_view"] = view_name
            client.hset(feature_key, mapping=serialized)

            new_last_id = msg_id
            print(f"Materialized {entity_id}: {features}")

    return new_last_id

# Run consumer loop
last_id = "0-0"
while True:
    last_id = consume_features("fs:stream:user_profile", last_id)
```

### With the Library

```python
# One-shot consume: read pending entries and write to Hashes
last_id = store.streaming.consume_once(
    user_features,
    last_id="0-0",   # Start from beginning
    count=100,        # Process up to 100 messages
    block_ms=1000,    # Block for 1 second if no messages
)

# Or start a background consumer thread
store.streaming.start_consumer(user_features)
# Consumer runs in background, materializing features as they arrive

# Later, stop it
store.streaming.stop_consumer()
```

**How it works:** `consume_once()` calls `XREAD` to fetch stream entries, deserializes the JSON features, then calls `write_batch()` which uses a pipeline of `HSET` commands to materialize all entities in one round-trip.

## Step 3: Batch Publishing

For high-throughput producers, publish multiple entities in one pipeline:

```python
# Publish 1000 entities in one pipeline
entity_features = {
    f"user_{i:03d}": {"age": 20 + i % 50, "segment": "premium"}
    for i in range(1000)
}

count = store.streaming.publish_batch(
    user_features,
    entity_features,
    maxlen=10000,
)
print(f"Published {count} entities to stream")
# Published 1000 entities to stream
```

## Step 4: Stream Management

```bash
# Check stream info
info = store.streaming.stream_info(user_features)
print(info)
# {'length': 1001, 'first_entry': ..., 'last_entry': ...}

# Trim old entries
store.streaming.trim_stream(user_features, maxlen=1000)

# Raw Valkey commands for stream inspection
length = client.xlen("fs:stream:user_profile")
info = client.xinfo_stream("fs:stream:user_profile")
print(f"Stream length: {length}")
```

## Consumer Groups (Distributed Processing)

For production, use consumer groups to distribute work across multiple workers:

```python
# Create a consumer group
stream_key = "fs:stream:user_profile"
try:
    client.xgroup_create(stream_key, "feature_writers", id="0", mkstream=True)
except valkey.ResponseError:
    pass  # Group already exists

# Consumer reads from the group
def consume_from_group(consumer_name: str):
    entries = client.xreadgroup(
        "feature_writers",  # group name
        consumer_name,            # consumer name
        {stream_key: ">"},        # ">" means new messages only
        count=50,
        block=2000,
    )

    if not entries:
        return

    for stream, messages in entries:
        for msg_id, data in messages:
            entity_id = data["entity_id"]
            features = json.loads(data["features"])

            # Write to online store
            feature_key = f"fs:v1:user_profile:{entity_id}"
            client.hset(feature_key, mapping={k: str(v) for k, v in features.items()})

            # Acknowledge processing
            client.xack(stream_key, "feature_writers", msg_id)

# Run workers (each on a different process/machine)
consume_from_group("worker-1")
consume_from_group("worker-2")
```

**Consumer Group Benefits:** Messages are distributed across workers - each message is delivered to exactly one consumer in the group. If a worker crashes, unacknowledged messages can be reclaimed with `XPENDING` and `XCLAIM`. This gives you at-least-once delivery semantics.

## Valkey Streams Command Reference

Operation| Command| Latency  
---|---|---  
Publish message| `XADD stream * field value ...`| ~0.1ms  
Read new messages| `XREAD COUNT 100 BLOCK 1000 STREAMS key id`| ~0.1ms + block  
Batch publish (pipeline)| Pipeline + `XADD`| ~2ms (1000 msgs)  
Trim stream| `XTRIM stream MAXLEN 10000`| ~0.1ms  
Stream length| `XLEN stream`| ~0.1ms  
Group read| `XREADGROUP GROUP name consumer ...`| ~0.1ms + block  
Acknowledge| `XACK stream group id`| ~0.1ms  
  
**Next up:** Learn how to serve feature vectors directly to ML models - scikit-learn, PyTorch, and LLM chains - with a FastAPI integration example.