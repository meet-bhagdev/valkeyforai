"""Tests for @betterdb/agent-cache - Agent Session Store."""

import pytest


@pytest.fixture
def valkey_client():
    """Create a Valkey client for testing."""
    import valkey

    client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)
    yield client
    client.close()


class TestAgentSessionStore:
    """Tests for cookbook: Agent Session Store."""

    def test_placeholder(self, valkey_client):
        """TODO: implement test for Agent Session Store."""
        assert valkey_client.ping()
