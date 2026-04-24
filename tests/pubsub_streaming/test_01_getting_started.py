"""Integration tests for Pub/Sub & Streaming - Getting Started with Pub/Sub.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with Pub/Sub."""

    # --- Block 1 ---
    import time
    import json

    client = client

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

    # --- Block 2 ---
    import json

    client = client

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

    # --- Block 3 ---
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

    # --- Block 4 ---
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

