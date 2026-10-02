"""Integration tests for Pub/Sub & Streaming - Production Patterns.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_06_production(client):
    """Run all code blocks from: Production Patterns."""

    # --- Block 1 ---
    import valkey, time
    client = client

    # Approximate trim (faster, recommended)
    client.xadd("ai:tasks", {"data": "..."}, maxlen=10000)

    # Time-based trim (remove entries older than 1 hour)
    cutoff_ms = int((time.time() - 3600) * 1000)
    client.xtrim("ai:tasks", minid=cutoff_ms)

    # --- Block 2 ---
    def stream_health(stream_key):
        info = client.xinfo_stream(stream_key)
        groups = client.xinfo_groups(stream_key)
        return {
            "length": info["length"],
            "groups": len(groups),
            "consumers": sum(g["consumers"] for g in groups),
            "pending": sum(g["pending"] for g in groups),
        }
    print(stream_health("ai:tasks"))

    # --- Block 3 ---
    def resilient_subscriber(channel):
        while True:
            try:
                c = client
                ps = c.pubsub()
                ps.subscribe(channel)
                print(f"Connected to {channel}")
                for msg in ps.listen():
                    if msg["type"] == "message":
                        print(msg["data"])
            except valkey.ConnectionError:
                print("Disconnected, reconnecting in 2s...")
                time.sleep(2)

    # --- Block 4 ---
    def process_with_dlq(stream, group, consumer, max_retries=3):
        entries = client.xreadgroup(group, consumer, {stream: ">"}, count=10, block=2000)
        if not entries: return
        for s, messages in entries:
            for msg_id, data in messages:
                try:
                    process(data)
                    client.xack(stream, group, msg_id)
                except Exception:
                    # After max retries, move to DLQ
                    pending = client.xpending_range(stream, group, msg_id, msg_id, 1)
                    if pending and pending[0]["times_delivered"] >= max_retries:
                        client.xadd(f"{stream}:dlq", data)
                        client.xack(stream, group, msg_id)

