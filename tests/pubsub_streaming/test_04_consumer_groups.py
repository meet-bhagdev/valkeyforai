"""Integration tests for Pub/Sub & Streaming - Consumer Groups.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_04_consumer_groups(client):
    """Run all code blocks from: Consumer Groups."""

    # --- Block 1 ---
    client = client

    try:
        client.xgroup_create("ai:tasks", "workers", id="0", mkstream=True)
    except valkey.ResponseError:
        pass  # Group already exists

    # --- Block 2 ---
    def worker(worker_name: str):
        while True:
            entries = client.xreadgroup(
                "workers", worker_name,
                {"ai:tasks": ">"},
                count=5, block=2000,
            )
            if not entries: continue
            for stream, messages in entries:
                for msg_id, data in messages:
                    print(f"[{worker_name}] Processing: {data}")
                    # Process the task...
                    client.xack("ai:tasks", "workers", msg_id)

