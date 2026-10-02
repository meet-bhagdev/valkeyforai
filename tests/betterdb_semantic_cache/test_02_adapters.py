"""Tests for @betterdb/semantic-cache - LangChain & Vercel AI Adapters."""

import pytest


@pytest.fixture
def valkey_client():
    """Create a Valkey client for testing."""
    import valkey

    client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)
    yield client
    client.close()


class TestLangChainVercelAIAdapters:
    """Tests for cookbook: LangChain & Vercel AI Adapters."""

    def test_placeholder(self, valkey_client):
        """TODO: implement test for LangChain & Vercel AI Adapters."""
        assert valkey_client.ping()
