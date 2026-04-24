"""Integration tests for RAG Pipelines - Cache Invalidation.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_04_cache_invalidation(client):
    """Run all code blocks from: Cache Invalidation."""

    # --- Block 1 ---
    # Or use Python helper
    def cache_with_ttl(key, data, ttl=3600):
        client.hset(key, mapping=data)
        client.expire(key, ttl)

    # --- Block 2 ---
    # Store current version
    SET cache:version 42

    # Include version in cache keys
    def get_cache_key(query):
        version = client.get("cache:version")
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"cache:v{version}:{query_hash}"

    # Invalidate ALL cache by bumping version
    def invalidate_all():
        client.incr("cache:version")
        # Old keys will miss and eventually expire

    # --- Block 3 ---
    # Track which cache entries depend on which documents
    def cache_response(query, response, source_docs):
        cache_key = get_cache_key(query)
        client.hset(cache_key, mapping={
            "query": query,
            "response": response,
            "sources": json.dumps(source_docs)
        })
        # Track dependency: doc -> cache entries
        for doc_id in source_docs:
            client.sadd(f"doc_deps:{doc_id}", cache_key)

    # When a document is updated
    def on_document_update(doc_id):
        # Get all cache entries that depend on this doc
        cache_keys = client.smembers(f"doc_deps:{doc_id}")
        # Delete them
        if cache_keys:
            client.delete(*cache_keys)
        # Clean up dependency tracking
        client.delete(f"doc_deps:{doc_id}")

    # --- Block 4 ---
    # Use namespaced prefixes
    # cache:docs:technical:...
    # cache:docs:support:...
    # cache:faqs:billing:...

    # Invalidate an entire namespace
    def invalidate_namespace(namespace):
        pattern = f"cache:{namespace}:*"
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=pattern, count=100)
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break

    # --- Block 5 ---
    class SmartCache:
        def __init__(self, default_ttl=3600):
            self.client = client
            self.default_ttl = default_ttl

        def set(self, query, response, sources=None, ttl=None):
            version = self.client.get("cache:version") or "1"
            key = f"cache:v{version}:{hash(query)}"
            self.client.hset(key, mapping={
                "response": response,
                "sources": json.dumps(sources or [])
            })
            self.client.expire(key, ttl or self.default_ttl)

            # Track dependencies
            for src in (sources or []):
                self.client.sadd(f"deps:{src}", key)

        def invalidate_source(self, source_id):
            keys = self.client.smembers(f"deps:{source_id}")
            if keys:
                self.client.delete(*keys)
            self.client.delete(f"deps:{source_id}")

        def invalidate_all(self):
            self.client.incr("cache:version")

