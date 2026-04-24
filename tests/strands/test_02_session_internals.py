"""Integration tests for Strands - Managing Session Data.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_02_session_internals(client):
    """Run all code blocks from: Managing Session Data."""

    # --- Block 1 ---
    from strands import Agent
    from strands_valkey_session_manager import ValkeySessionManager

    # In a new Python process - history is restored from Valkey
    client = client
    session_manager = ValkeySessionManager(
        session_id="user-42",  # same session ID
        client=client,
    )
    agent = Agent(session_manager=session_manager)

    response = agent("What was I just telling you about?")
    print(response)
    # Agent correctly recalls: "You mentioned you're building a RAG pipeline."

    # --- Block 2 ---
    # List all messages for this session
    messages = session_manager.list_messages()
    for msg in messages:
        print(f"[{msg['role']}] {str(msg['content'])[:80]}")

    # Or inspect raw keys directly
    keys = client.keys("session:user-42*")
    for k in sorted(keys):
        print(k)

    # --- Block 3 ---
    from strands_valkey_session_manager import ValkeySessionManager

    client = client
    sm = ValkeySessionManager(session_id="user-42", client=client)

    # Read session metadata
    session = sm.read_session("user-42")
    print(f"Created: {session.created_at}")

    # Read agent state
    agent_state = sm.read_agent("user-42", "default")
    print(f"Message count: {agent_state.conversation_manager_state}")

    # List all messages in order
    messages = sm.list_messages()
    print(f"{len(messages)} messages in session")
    for msg in messages:
        text_blocks = [b["text"] for b in msg.content if "text" in b]
        preview = text_blocks[0][:80] if text_blocks else "[tool use/result]"
        print(f"  [{msg.role:9}] {preview}")

