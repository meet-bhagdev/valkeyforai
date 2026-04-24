"""Integration tests for Mem0 - Production with ElastiCache.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_production(raw_client):
    """Run all code blocks from: Production with ElastiCache."""

    # --- Block 1 ---

    # Connect directly to check index health
    client = valkey.from_url("valkey://your-cluster:6379")

    # Check index info
    info = client.execute_command("FT.INFO", "prod_memories")
    print(info)

    # Check memory usage
    mem_info = client.info("memory")
    print(f"Used: {mem_info['used_memory_human']}")

    # Count memories per user
    results = client.execute_command(
        "FT.SEARCH", "prod_memories",
        "@user_id:{alice}",
        "LIMIT", "0", "0",  # count only
    )
    print(f"Alice has {results[0]} memories")

