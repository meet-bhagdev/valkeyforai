"""Tests for @betterdb/agent-cache - Getting Started with @betterdb/agent-cache."""

import pytest


@pytest.fixture
def valkey_client():
    """Create a Valkey client for testing."""
    import valkey

    client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)
    yield client
    client.close()


class TestGettingStartedWithBetterdbagentcache:
    """Tests for cookbook: Getting Started with @betterdb/agent-cache."""

    def test_placeholder(self, valkey_client):
        """TODO: implement test for Getting Started with @betterdb/agent-cache."""
        assert valkey_client.ping()
