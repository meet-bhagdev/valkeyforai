"""Integration tests for CrewAI - Getting Started with CrewAI + Valkey.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with CrewAI + Valkey."""

    # --- Block 1 ---
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class ValkeyConfig:
        host: str
        port: int
        use_tls: bool
        password: str | None

    def get_valkey_config() -> ValkeyConfig:
        return ValkeyConfig(
            host=os.environ.get("VALKEY_HOST", "localhost"),
            port=int(os.environ.get("VALKEY_PORT", "6379")),
            use_tls=os.environ.get("VALKEY_TLS", "false").lower() in ("true", "1"),
            password=os.environ.get("VALKEY_PASSWORD") or None,
        )

    # --- Block 2 ---
    import asyncio
    from glide import GlideClient, GlideClientConfiguration, NodeAddress

    async def test_connection():
        config = get_valkey_config()
        glide_config = GlideClientConfiguration(
            [NodeAddress(config.host, config.port)],
            use_tls=config.use_tls,
        )
        client = await GlideClient.create(glide_config)

        # Test basic operations
        await client.set("test:hello", "world")
        val = await client.get("test:hello")
        print(f"✅ Connected! Got: {val.decode()}")

        # Clean up
        await client.delete(["test:hello"])

    asyncio.run(test_connection())
    # ✅ Connected! Got: world

