"""Integration tests for Strands - Getting Started with Strands + Valkey.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with Strands + Valkey."""

    # --- Block 1 ---
    from strands_valkey_session_manager import ValkeySessionManager

    # Connect to Valkey
    client = client

    # Create the session manager - one per session
    session_manager = ValkeySessionManager(
        session_id="user-42",
        client=client,
    )

    # --- Block 2 ---
    from strands import Agent

    agent = Agent(
        system_prompt="You are a helpful assistant.",
        session_manager=session_manager,
    )

    # Strands automatically persists every turn to Valkey
    response = agent("My name is Alex and I'm building a RAG pipeline.")
    print(response)

