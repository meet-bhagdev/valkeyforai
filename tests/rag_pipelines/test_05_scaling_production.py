"""Integration tests for RAG Pipelines - Scaling for Production.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_05_scaling_production(client):
    """Run all code blocks from: Scaling for Production."""

    # --- Block 1 ---
    # Connect to replicas for read scaling
    primary = client
    replica = client

    # Write to primary, read from replicas
    primary.hset(key, mapping=data)
    results = replica.ft('idx').search(query)

    # --- Block 2 ---
    # Use connection pools in production
    pool = valkey.ConnectionPool(
        host='localhost',
        port=6379,
        max_connections=50,
        decode_responses=False
    )
    client = client

    # Or use async with connection pool
    pool = valkey.asyncio.ConnectionPool.from_url(
        "valkey://localhost:6379",
        max_connections=50
    )

    # --- Block 3 ---
    # Connect to ElastiCache cluster
    client = client

    # For cluster mode


    from valkey.cluster import ValkeyCluster

    cluster = ValkeyCluster(
        host='my-cluster.cache.amazonaws.com',
        port=6379,
        ssl=True
    )

