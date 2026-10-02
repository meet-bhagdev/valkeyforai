"""Integration tests for Pub/Sub & Streaming - Fan-Out Patterns.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_05_fan_out_patterns(client):
    """Run all code blocks from: Fan-Out Patterns."""

    # --- Block 1 ---
    import valkey, json, time
    client = client

    def broadcast_agent_event(agent_id, event_type, payload):
        """Broadcast to all subscribers watching this agent."""
        channel = f"agent:{agent_id}:events"
        message = {"type": event_type, "data": payload, "ts": time.time()}
        n = client.publish(channel, json.dumps(message))
        return n  # Number of receivers

    # Dashboard, logger, metrics all receive this:
    broadcast_agent_event("agent-1", "tool_call", {"tool": "search", "query": "valkey"})

    # --- Block 2 ---
    # Multiple consumer groups on the SAME stream
    # Each group gets ALL messages independently
    client.xgroup_create("ai:events", "loggers", id="0", mkstream=True)
    client.xgroup_create("ai:events", "metrics", id="0", mkstream=True)
    client.xgroup_create("ai:events", "alerts", id="0", mkstream=True)

    # Producer writes once
    client.xadd("ai:events", {"event": "model_prediction", "latency_ms": "45"})
    # All 3 groups get the message independently

    # --- Block 3 ---
    def publish_with_durability(event):
        """Write to Stream (durable) AND Pub/Sub (live)."""
        payload = json.dumps(event)
        client.xadd("ai:events", {"data": payload}, maxlen=50000)
        client.publish("ai:events:live", payload)

