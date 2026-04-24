"""Integration tests for Context Engineering - Context Engineering Fundamentals.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_fundamentals(client):
    """Run all code blocks from: Context Engineering Fundamentals."""

    # --- Block 1 ---
    import json

    client = client

    # Store agent configuration
    client.hset("agent:config:support_bot", mapping={
        "role": "You are a helpful customer support agent for Acme Corp.",
        "constraints": "Always be polite. Never share internal pricing. Escalate billing issues.",
        "output_format": "Respond in markdown. Keep answers under 200 words.",
        "tools_available": json.dumps(["search_kb", "check_order", "create_ticket"]),
    })
    print("System instructions stored")

    # --- Block 2 ---
    import time

    def add_message(session_id: str, role: str, content: str):
        """Append a message to the conversation history."""
        msg = json.dumps({"role": role, "content": content, "ts": time.time()})
        client.rpush(f"chat:{session_id}", msg)
        # Keep only last 50 messages (sliding window)
        client.ltrim(f"chat:{session_id}", -50, -1)
        # Set TTL for session cleanup (30 min inactivity)
        client.expire(f"chat:{session_id}", 1800)

    def get_history(session_id: str, last_n: int = 10) -> list:
        """Retrieve recent conversation history."""
        raw = client.lrange(f"chat:{session_id}", -last_n, -1)
        return [json.loads(m) for m in raw]

    # Example conversation
    add_message("sess_001", "user", "What's your refund policy?")
    add_message("sess_001", "assistant", "Our refund policy allows returns within 30 days...")
    add_message("sess_001", "user", "Can I return an opened item?")

    history = get_history("sess_001")
    for msg in history:
        print(f"  {msg['role']}: {msg['content'][:60]}...")

    # --- Block 3 ---
    def store_tool_output(session_id: str, step: int, tool_name: str, result: dict):
        """Store the output of a tool call for context assembly."""
        key = f"tool:{session_id}:step_{step}"
        client.hset(key, mapping={
            "tool": tool_name,
            "result": json.dumps(result),
            "timestamp": str(time.time()),
        })
        client.expire(key, 3600)  # 1 hour TTL

    def get_tool_outputs(session_id: str) -> list:
        """Retrieve all tool outputs for this session."""
        keys = client.keys(f"tool:{session_id}:step_*")
        outputs = []
        for key in sorted(keys):
            data = client.hgetall(key)
            outputs.append({
                "tool": data["tool"],
                "result": json.loads(data["result"]),
            })
        return outputs

    # Example: agent called the order lookup tool
    store_tool_output("sess_001", 1, "check_order", {
        "order_id": "ORD-12345",
        "status": "delivered",
        "date": "2025-03-15",
    })

    # --- Block 4 ---
    def remember(user_id: str, key: str, value: str):
        """Store a long-term memory about a user."""
        client.hset(f"memory:{user_id}", key, value)
        # No TTL - persists across sessions

    def recall(user_id: str) -> dict:
        """Retrieve all memories about a user."""
        return client.hgetall(f"memory:{user_id}")

    # Store user preferences
    remember("alice", "preferred_language", "English")
    remember("alice", "tier", "premium")
    remember("alice", "last_issue", "billing dispute on ORD-12345")

    memories = recall("alice")
    print(f"Alice's memories: {memories}")

