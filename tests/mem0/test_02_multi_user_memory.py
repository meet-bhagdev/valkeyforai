"""Integration tests for Mem0 - Multi-User Memory.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_02_multi_user_memory(client):
    """Run all code blocks from: Multi-User Memory."""

    # --- Block 1 ---
    # User Alice
    memory.add(
        [{"role": "user", "content": "I prefer dark mode and Python."}],
        user_id="alice",
    )

    # User Bob
    memory.add(
        [{"role": "user", "content": "I use TypeScript and like light mode."}],
        user_id="bob",
    )

    # Search for Alice - only gets Alice's memories
    alice_results = memory.search("What are the user preferences?", user_id="alice")
    print("Alice:", [r["memory"] for r in alice_results["results"]])
    # Alice: ['Prefers dark mode and Python']

    # Search for Bob - only gets Bob's memories
    bob_results = memory.search("What are the user preferences?", user_id="bob")
    print("Bob:", [r["memory"] for r in bob_results["results"]])
    # Bob: ['Uses TypeScript and likes light mode']

    # --- Block 2 ---
    # Support agent knowledge
    memory.add(
        [{"role": "user", "content": "Our refund policy is 30 days for unused items."}],
        agent_id="support_bot",
    )

    # Sales agent knowledge
    memory.add(
        [{"role": "user", "content": "Current promotion: 20% off all premium plans."}],
        agent_id="sales_bot",
    )

    # Each agent only sees its own knowledge
    support_results = memory.search("What is the refund policy?", agent_id="support_bot")
    sales_results = memory.search("Any promotions?", agent_id="sales_bot")

    # --- Block 3 ---
    # Add a memory scoped to both user AND agent
    memory.add(
        [{"role": "user", "content": "I had an issue with order #12345."}],
        user_id="alice",
        agent_id="support_bot",
    )

    # Search: finds Alice's support interactions only
    results = memory.search(
        "Previous issues",
        user_id="alice",
        agent_id="support_bot",
    )

