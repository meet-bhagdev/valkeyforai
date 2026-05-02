"""Shared fixtures for all cookbook integration tests.

These tests require:
- Valkey running with search module: docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:9-alpine
- OPENAI_API_KEY set in .env or environment (for cookbooks that use OpenAI)
"""

import pytest
import valkey
import os
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session")
def valkey_url():
    """Valkey connection URL."""
    return os.environ.get("VALKEY_URL", "valkey://localhost:6379")


@pytest.fixture
def client():
    """Valkey client with decode_responses=True."""
    c = valkey.Valkey(
        host=os.environ.get("VALKEY_HOST", "localhost"),
        port=int(os.environ.get("VALKEY_PORT", 6379)),
        decode_responses=True,
    )
    yield c
    c.close()


@pytest.fixture
def raw_client():
    """Valkey client without decode_responses (for binary/vector ops)."""
    c = valkey.Valkey(
        host=os.environ.get("VALKEY_HOST", "localhost"),
        port=int(os.environ.get("VALKEY_PORT", 6379)),
    )
    yield c
    c.close()


@pytest.fixture
def openai_client():
    """OpenAI client. Requires OPENAI_API_KEY in env."""
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)


@pytest.fixture
def openai_model():
    """OpenAI model to use. Defaults to gpt-4o-mini for cost efficiency."""
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


@pytest.fixture(autouse=True)
def _check_valkey(client):
    """Skip all tests if Valkey is not reachable."""
    try:
        client.ping()
    except valkey.ConnectionError:
        pytest.skip("Valkey not available")
