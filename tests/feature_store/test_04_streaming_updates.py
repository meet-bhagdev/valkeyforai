"""Integration tests for Feature Store - Streaming Updates.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_04_streaming_updates(client):
    """Run all code blocks from: Streaming Updates."""

    # --- Block 1 ---
    import json
    import time

    client = client

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

    # --- Block 2 ---
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

    # --- Block 3 ---
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

    # --- Block 4 ---
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

    # --- Block 5 ---
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

    # --- Block 6 ---
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

