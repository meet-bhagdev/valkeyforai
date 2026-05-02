## Why Valkey for Feature Stores?

ML models need features at inference time. A feature store bridges offline training and online serving. Valkey is the ideal online store because:

  * **Sub-millisecond reads** - HGETALL returns a full feature vector in ~0.1ms
  * **Atomic writes** - HSET updates features without race conditions
  * **Built-in TTL** - Stale features expire automatically with EXPIRE
  * **Batch pipelines** - Fetch 100 entities in ~0.3ms with pipelining

## Prerequisites

  * Docker installed (or a running Valkey instance)
  * Python 3.12+

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9-alpine
```

Verify it's running:

```bash
docker exec valkey valkey-cli ping
# PONG
```

## Step 2: Install Dependencies

```bash
uv pip install valkey python-dotenv
```

The `valkey` package is the official Valkey Python client - no special drivers needed.

## Step 3: Understand the Data Model

Every entity's features are stored as a **Valkey Hash** :

```python
# Key format: fs:v1:{feature_view_name}:{entity_id}
# Example:
fs:v1:user_profile:user_123 → {
    age: "28",
    lifetime_value: "1250.50",
    segment: "premium",
    _updated_at: "1710000000.0",
    _feature_view: "user_profile"
}
```

**How it works:** Valkey Hashes map perfectly to feature vectors. Each field is a feature, each key is an entity. One `HGETALL` returns the full feature vector. One `HMGET` returns selective features. Both complete in ~0.1ms.

## Step 4: Write Features with Raw Valkey Commands

Starting with raw Valkey commands to see what's happening under the hood:

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Write features for a user
key = "fs:v1:user_profile:user_001"
features = {
    "age": "28",
    "lifetime_value": "1250.50",
    "segment": "premium",
    "_updated_at": str(time.time()),
    "_feature_view": "user_profile",
}

# HSET - write all features atomically
client.hset(key, mapping=features)

# Set TTL - features expire after 1 hour
client.expire(key, 3600)

print("✅ Features written")
```

## Step 5: Read Features Back

```python
# HGETALL - read all features for an entity
result = client.hgetall("fs:v1:user_profile:user_001")
print(result)
# {'age': '28', 'lifetime_value': '1250.50', 'segment': 'premium', ...}

# HMGET - read only specific features
age, ltv = client.hmget("fs:v1:user_profile:user_001", ["age", "lifetime_value"])
print(f"age={age}, ltv={ltv}")
# age=28, ltv=1250.50
```

## Step 6: Use the Library

Here's the same thing with the feature store library, which handles serialization, TTL, and metadata for you.

**Note:** This step uses the feature store library from the [valkeyforai GitHub repo](https://github.com/meet-bhagdev/valkeyforai). Clone it first:

```bash
git clone https://github.com/meet-bhagdev/valkeyforai && cd valkeyforai
```

```python
from src import ValkeyFeatureStore, Entity, FeatureView, Feature, FeatureType

# Connect
store = ValkeyFeatureStore(host="localhost", port=6379)

# Define an entity
user = Entity(name="user", join_keys=["user_id"])

# Define a feature view (schema for this entity's features)
user_features = FeatureView(
    name="user_profile",
    entity=user,
    features=[
        Feature("age", FeatureType.INT),
        Feature("lifetime_value", FeatureType.FLOAT),
        Feature("segment", FeatureType.STRING),
    ],
    ttl=3600,  # 1 hour
)

# Register it with the store
store.register(user_features)

# Write - automatically serializes, sets TTL, adds metadata
store.write("user_profile", "user_001", {
    "age": 28,
    "lifetime_value": 1250.50,
    "segment": "premium",
})

# Read - automatically deserializes to correct Python types
features = store.read("user_profile", "user_001")
print(features)
# {'age': 28, 'lifetime_value': 1250.5, 'segment': 'premium'}
# Note: age is int, ltv is float - types are preserved!
```

## How It Works Under the Hood

Operation| Valkey Command| Latency  
---|---|---  
Write features| `HSET key field1 val1 field2 val2 ...`| ~0.1ms  
Set TTL| `EXPIRE key 3600`| ~0.1ms  
Write + TTL (pipelined)| `HSET` \+ `EXPIRE` in pipeline| ~0.2ms  
Read all features| `HGETALL key`| ~0.1ms  
Read specific features| `HMGET key field1 field2`| ~0.1ms  
  
**Next up:** In the next cookbook, we'll cover batch serving - fetching features for 100+ entities in a single round-trip using Valkey pipelines.

[ Next → 02 - Online Feature Serving ](<02-online-serving.html>)