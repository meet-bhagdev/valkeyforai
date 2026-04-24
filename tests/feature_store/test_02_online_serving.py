"""Integration tests for Feature Store - Online Feature Serving.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_02_online_serving(client):
    """Run all code blocks from: Online Feature Serving."""

    # --- Block 1 ---
    # Prediction request arrives
    user_id = "user_123"

    # 1. Fetch features from online store  ← This must be FAST
    # 2. Assemble feature vector
    # 3. Run model.predict(features)
    # 4. Return prediction

    # --- Block 2 ---

    client = client

    # Fetch all features for user_123
    raw = client.hgetall("fs:v1:user_profile:user_123")
    # {'age': '28', 'lifetime_value': '1250.50', 'segment': 'premium', ...}

    # Filter out internal metadata
    features = {k: v for k, v in raw.items() if not k.startswith("_")}
    # {'age': '28', 'lifetime_value': '1250.50', 'segment': 'premium'}

    # --- Block 3 ---
    from src import ValkeyFeatureStore, Entity, FeatureView, Feature, FeatureType

    store = ValkeyFeatureStore(host="localhost", port=6379)
    # ... register feature views ...

    # All features (uses HGETALL internally)
    features = store.read("user_profile", "user_123")
    # {'age': 28, 'lifetime_value': 1250.5, 'segment': 'premium'}

    # Selective features (uses HMGET internally)
    features = store.read("user_profile", "user_123", ["age", "lifetime_value"])
    # {'age': 28, 'lifetime_value': 1250.5}

    # --- Block 4 ---
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

    # --- Block 5 ---
    # Batch read - uses pipeline internally
    entity_ids = [f"user_{i:03d}" for i in range(100)]
    batch = store.read_batch("user_profile", entity_ids)

    # Returns: {'user_000': {'age': 28, ...}, 'user_001': {'age': 35, ...}, ...}
    print(f"Fetched {len(batch)} entities")

    # --- Block 6 ---
    user_id = "user_123"

    pipe = client.pipeline(transaction=False)
    # Fetch from user_profile view
    pipe.hmget(f"fs:v1:user_profile:{user_id}", ["age", "lifetime_value"])
    # Fetch from user_risk view
    pipe.hmget(f"fs:v1:user_risk_profile:{user_id}", ["fraud_score", "txn_count_24h"])

    results = pipe.execute()
    # results[0] = ['28', '1250.50']       ← from user_profile
    # results[1] = ['0.05', '12']           ← from user_risk_profile

    # --- Block 7 ---
    # Set during write (the library does this automatically)
    pipe = client.pipeline(transaction=True)
    pipe.hset(key, mapping=features)
    pipe.expire(key, 3600)  # 1 hour TTL
    pipe.execute()

    # Check remaining TTL
    ttl = client.ttl("fs:v1:user_profile:user_123")
    print(f"Expires in {ttl} seconds")

