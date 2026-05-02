"""Integration tests for Context Engineering - Production Context Management.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_production(client):
    """Run all code blocks from: Production Context Management."""

    # --- Block 1 ---
    import json
    import time

    client = client

    # Short-term memory: active session context (low TTL)
    def store_short_term(session_id: str, key: str, value: str, ttl: int = 1800):
        """Store session-scoped context that expires after inactivity."""
        client.hset(f"session:{session_id}", key, value)
        client.expire(f"session:{session_id}", ttl)

    # Long-term memory: persists across sessions (no TTL or high TTL)
    def store_long_term(user_id: str, key: str, value: str):
        """Store cross-session user knowledge that persists indefinitely."""
        client.hset(f"memory:{user_id}", key, value)
        # No EXPIRE - this persists

    # Example
    store_short_term("sess_100", "current_topic", "billing")
    store_short_term("sess_100", "escalation_level", "0")
    store_long_term("alice", "communication_style", "prefers concise answers")
    store_long_term("alice", "timezone", "America/Los_Angeles")

    # --- Block 2 ---
    def prune_old_messages(session_id: str, max_messages: int = 20):
        """Keep only the most recent messages."""
        client.ltrim(f"chat:{session_id}", -max_messages, -1)

    def summarize_and_store(user_id: str, session_id: str, summary: str):
        """After a session ends, store a summary for long-term recall."""
        date = time.strftime("%Y-%m-%d")
        client.hset(f"summary:{user_id}:{date}", mapping={
            "session_id": session_id,
            "summary": summary,
            "timestamp": str(time.time()),
        })
        client.expire(f"summary:{user_id}:{date}", 86400 * 30)  # 30 days

    # Prune chat to last 20 messages
    prune_old_messages("sess_100")

    # Store session summary for future context
    summarize_and_store("alice", "sess_100", 
        "User asked about billing. Resolved a refund request for order ORD-12345.")

    # --- Block 3 ---
    def get_user_context(user_id: str, session_id: str) -> dict:
        """Get all context for a specific user, properly isolated."""
        return {
            "memory": client.hgetall(f"memory:{user_id}"),
            "session": client.hgetall(f"session:{session_id}"),
            "history": [
                json.loads(m) for m in 
                client.lrange(f"chat:{session_id}", -10, -1)
            ],
        }

    # Alice's context is completely separate from Bob's
    alice_ctx = get_user_context("alice", "sess_alice_001")
    bob_ctx = get_user_context("bob", "sess_bob_001")

    # --- Block 4 ---
    def record_context_metrics(session_id: str, metrics: dict):
        """Track context assembly metrics."""
        client.hset(f"metrics:context:{session_id}", mapping={
            "sources_used": str(metrics.get("sources_used", 0)),
            "total_tokens": str(metrics.get("total_tokens", 0)),
            "assembly_time_ms": str(metrics.get("assembly_time_ms", 0)),
            "pruned_messages": str(metrics.get("pruned_messages", 0)),
            "timestamp": str(time.time()),
        })
        client.expire(f"metrics:context:{session_id}", 86400 * 7)  # 7 days

    # After assembling context
    record_context_metrics("sess_100", {
        "sources_used": 4,
        "total_tokens": 2850,
        "assembly_time_ms": 3.2,
        "pruned_messages": 5,
    })

    # Aggregate metrics
    def get_avg_assembly_time(pattern: str = "metrics:context:*") -> float:
        """Calculate average context assembly time."""
        keys = client.keys(pattern)
        times = []
        for key in keys[:100]:  # Sample last 100 sessions
            t = client.hget(key, "assembly_time_ms")
            if t:
                times.append(float(t))
        return sum(times) / len(times) if times else 0.0

