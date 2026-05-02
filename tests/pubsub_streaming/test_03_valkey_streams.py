"""Integration tests for Pub/Sub & Streaming - Valkey Streams.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_valkey_streams(client):
    """Run all code blocks from: Valkey Streams."""

    # --- Block 1 ---
    import valkey, json, time
    client = client

    # XADD - append to stream
    entry_id = client.xadd("ai:tasks", {
        "type": "embedding",
        "text": "Hello world",
        "model": "text-embedding-3-small",
    })
    print(f"Added: {entry_id}")

    # With MAXLEN cap
    client.xadd("ai:tasks", {"type": "completion"}, maxlen=10000)

    # --- Block 2 ---
    # XREAD - blocking read for new messages
    entries = client.xread({"ai:tasks": "0-0"}, count=10, block=5000)
    for stream, messages in entries:
        for msg_id, data in messages:
            print(f"[{msg_id}] {data}")

    # XRANGE - replay from beginning
    messages = client.xrange("ai:tasks", min="-", max="+", count=5)

    # XREVRANGE - newest first
    latest = client.xrevrange("ai:tasks", max="+", min="-", count=1)

    # --- Block 3 ---
    length = client.xlen("ai:tasks")
    info = client.xinfo_stream("ai:tasks")
    client.xtrim("ai:tasks", maxlen=1000)

    # --- Block 4 ---
    def consume(stream_key):
        last_id = "$"  # Only new messages
        while True:
            entries = client.xread({stream_key: last_id}, count=10, block=2000)
            if not entries: continue
            for stream, messages in entries:
                for msg_id, data in messages:
                    print(f"Processing: {data}")
                    last_id = msg_id

