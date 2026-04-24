"""Integration tests for Strands - Managing Your ValkeySession Store.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_managing_your_session_store(client):
    """Run all code blocks from: Managing Your ValkeySession Store."""

    # --- Block 1 ---
    from strands import Agent
    from strands_valkey_session_manager import ValkeySessionManager

    client = client

    # Two agents sharing the same session_id
    researcher = Agent(
        system_prompt="You are a research agent.",
        session_manager=ValkeySessionManager(
            session_id="workflow-001", client=client
        ),
    )
    writer = Agent(
        system_prompt="You are a writing agent.",
        session_manager=ValkeySessionManager(
            session_id="workflow-001", client=client
        ),
    )

    researcher("Research the key benefits of Valkey for AI workloads.")
    writer("Write a short blog intro about Valkey for AI.")

    # Each agent has its own message keys under the same session
    # session:workflow-001:agent:researcher:message:<id>
    # session:workflow-001:agent:writer:message:<id>

    # --- Block 2 ---
    from strands_valkey_session_manager import ValkeySessionManager

    client = client
    sm = ValkeySessionManager(session_id="user-42", client=client)

    # Removes session, agent state, and all messages for this session
    sm.delete_session("user-42")
    print("Session deleted")

    # --- Block 3 ---
    # List all keys for a session with their TTLs
    keys = client.keys("session:user-42*")
    for k in sorted(keys):
        ttl = client.ttl(k)
        print(f"{k}  (TTL: {ttl}s)")

    # session:user-42                                              (TTL: 3598s)
    # session:user-42:agent:default                                (TTL: 3597s)
    # session:user-42:agent:default:message:<uuid>                 (TTL: 3596s)
    # session:user-42:agent:default:message:<uuid>                 (TTL: 3596s)

