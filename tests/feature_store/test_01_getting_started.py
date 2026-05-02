"""Integration tests for Feature Store - Getting Started with Feature Store.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with Feature Store."""

    # --- Block 1 ---
    import time

    client = client

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

    # --- Block 2 ---
    # HGETALL - read all features for an entity
    result = client.hgetall("fs:v1:user_profile:user_001")
    print(result)
    # {'age': '28', 'lifetime_value': '1250.50', 'segment': 'premium', ...}

    # HMGET - read only specific features
    age, ltv = client.hmget("fs:v1:user_profile:user_001", ["age", "lifetime_value"])
    print(f"age={age}, ltv={ltv}")
    # age=28, ltv=1250.50

    # --- Block 3 ---
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

