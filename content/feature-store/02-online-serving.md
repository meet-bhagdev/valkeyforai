## The Inference-Time Challenge

When your ML model gets a prediction request, it needs a feature vector _fast_. The typical flow:

```python
# Prediction request arrives
user_id = "user_123"

# 1. Fetch features from online store  ← This must be FAST
# 2. Assemble feature vector
# 3. Run model.predict(features)
# 4. Return prediction
```

If your feature lookup takes 50ms, your entire prediction pipeline is bottlenecked. Valkey gives you ~0.1ms.

## Pattern 1: Single Entity Lookup

The simplest pattern — fetch all features for one entity:

### Raw Valkey: HGETALL

```python
import valkey

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Fetch all features for user_123
raw = client.hgetall("fs:v1:user_profile:user_123")
# {'age': '28', 'lifetime_value': '1250.50', 'segment': 'premium', ...}

# Filter out internal metadata
features = {k: v for k, v in raw.items() if not k.startswith("_")}
# {'age': '28', 'lifetime_value': '1250.50', 'segment': 'premium'}
```

### Raw Valkey: HMGET (selective fields)

If you only need 2 of 20 features, `HMGET` is more efficient:

```python
# Fetch only age and lifetime_value
age, ltv = client.hmget("fs:v1:user_profile:user_123", ["age", "lifetime_value"])
# age='28', ltv='1250.50'
```

### With the Library

```python
from src import ValkeyFeatureStore, Entity, FeatureView, Feature, FeatureType

store = ValkeyFeatureStore(host="localhost", port=6379)
# ... register feature views ...

# All features (uses HGETALL internally)
features = store.read("user_profile", "user_123")
# {'age': 28, 'lifetime_value': 1250.5, 'segment': 'premium'}

# Selective features (uses HMGET internally)
features = store.read("user_profile", "user_123", ["age", "lifetime_value"])
# {'age': 28, 'lifetime_value': 1250.5}
```

## Pattern 2: Batch Entity Lookup

In recommendation systems, you often need features for 100+ candidate items in one request. Making 100 individual calls would be slow. Instead, use **Valkey pipelines** :

### Raw Valkey: Pipelined HGETALL

```python
entity_ids = [f"user_{i:03d}" for i in range(100)]

# Pipeline sends all commands in ONE round-trip
pipe = client.pipeline(transaction=False)
for eid in entity_ids:
    pipe.hgetall(f"fs:v1:user_profile:{eid}")

# Execute all 100 HGETALL commands at once
results = pipe.execute()

# Map results back to entity IDs
batch = {}
for eid, raw in zip(entity_ids, results):
    if raw:
        batch[eid] = {k: v for k, v in raw.items() if not k.startswith("_")}

print(f"Fetched features for {len(batch)} entities")
```

### With the Library

```python
# Batch read — uses pipeline internally
entity_ids = [f"user_{i:03d}" for i in range(100)]
batch = store.read_batch("user_profile", entity_ids)

# Returns: {'user_000': {'age': 28, ...}, 'user_001': {'age': 35, ...}, ...}
print(f"Fetched {len(batch)} entities")
```

## Pattern 3: Multi-View Feature Vector

ML models often need features from multiple views. For example, a fraud model needs both user profile features and transaction features:

### Raw Valkey: Pipelined cross-view

```python
user_id = "user_123"

pipe = client.pipeline(transaction=False)
# Fetch from user_profile view
pipe.hmget(f"fs:v1:user_profile:{user_id}", ["age", "lifetime_value"])
# Fetch from user_risk view
pipe.hmget(f"fs:v1:user_risk_profile:{user_id}", ["fraud_score", "txn_count_24h"])

results = pipe.execute()
# results[0] = ['28', '1250.50']       ← from user_profile
# results[1] = ['0.05', '12']           ← from user_risk_profile
```

### With the Library

```python
# get_feature_vector fetches from multiple views in one pipeline
vector = store.get_feature_vector(
    "user_123",
    [
        "user_profile:age",
        "user_profile:lifetime_value",
        "user_risk_profile:fraud_score",
        "user_risk_profile:txn_count_24h",
    ],
)
# {'user_profile__age': 28, 'user_profile__lifetime_value': 1250.5,
#  'user_risk_profile__fraud_score': 0.05, 'user_risk_profile__txn_count_24h': 12}
```

**Key Insight:** `get_feature_vector()` groups the feature references by view, then uses `HMGET` for each view in a single pipeline. One round-trip fetches from all views, regardless of how many.

## Latency Benchmarks

Operation| Valkey Command| Entities| Latency  
---|---|---|---  
Single read (all fields)| `HGETALL`| 1| ~0.1ms  
Single read (2 fields)| `HMGET`| 1| ~0.1ms  
Batch read| Pipeline + `HGETALL`| 100| ~0.3ms  
Multi-view vector| Pipeline + `HMGET`| 1 (3 views)| ~0.15ms  
Batch write| Pipeline + `HSET`| 100| ~0.5ms  
Batch write| Pipeline + `HSET`| 1,000| ~5ms  
  
## TTL-Based Feature Expiry

Features go stale. A user's click-through rate from 2 days ago isn't useful for real-time ranking. Use `EXPIRE` to auto-clean:

```python
# Set during write (the library does this automatically)
pipe = client.pipeline(transaction=True)
pipe.hset(key, mapping=features)
pipe.expire(key, 3600)  # 1 hour TTL
pipe.execute()

# Check remaining TTL
ttl = client.ttl("fs:v1:user_profile:user_123")
print(f"Expires in {ttl} seconds")
```

**What's Next:** Learn how to compute real-time aggregation features (sliding window counts, rolling averages, cardinality) directly in Valkey.