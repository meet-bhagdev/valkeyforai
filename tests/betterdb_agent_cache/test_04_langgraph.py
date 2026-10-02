"""Tests for @betterdb/agent-cache - LangGraph Checkpointing."""

import pytest


@pytest.fixture
def valkey_client():
    """Create a Valkey client for testing."""
    import valkey

    client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)
    yield client
    client.close()


class TestLangGraphCheckpointing:
    """Tests for cookbook: LangGraph Checkpointing."""

    def test_placeholder(self, valkey_client):
        """TODO: implement test for LangGraph Checkpointing."""
        assert valkey_client.ping()
