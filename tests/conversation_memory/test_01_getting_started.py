"""Integration tests for Conversation Memory - Getting Started with Conversation Memory.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with Conversation Memory."""

    # --- Block 1 ---
    import asyncio
    import json
    from glide import GlideClient, GlideClientConfiguration, NodeAddress


    async def main():
        # Connect to Valkey with GLIDE
        config = GlideClientConfiguration([NodeAddress("localhost", 6379)])
        client = await GlideClient.create(config)

        session_id = "sess_abc123"
        key = f"chat:{session_id}"

        # Store a conversation
        messages = [
            {"role": "user", "content": "What is Valkey?"},
            {"role": "assistant", "content": "Valkey is an open-source, high-performance key-value store."},
            {"role": "user", "content": "How fast is it?"},
            {"role": "assistant", "content": "Sub-millisecond latency for most operations."},
        ]

        for msg in messages:
            await client.rpush(key, [json.dumps(msg)])

        # Set TTL - session expires after 1 hour
        await client.expire(key, 3600)

        print("✅ Conversation stored")


    asyncio.run(main())

    # --- Block 2 ---
    async def get_history(client, session_id, last_n=50):
        """Retrieve the last N messages from a conversation."""
        key = f"chat:{session_id}"

        # LRANGE with negative indices = last N messages
        raw = await client.lrange(key, -last_n, -1)

        return [json.loads(msg) for msg in raw]


    # Usage
    history = await get_history(client, "sess_abc123")
    for msg in history:
        print(f"{msg['role']}: {msg['content']}")

    # user: What is Valkey?
    # assistant: Valkey is an open-source, high-performance key-value store.
    # user: How fast is it?
    # assistant: Sub-millisecond latency for most operations.

    # --- Block 3 ---
    import boto3, json

    async def chat(client, session_id, user_message):
        # 1. Save the user message
        key = f"chat:{session_id}"
        await client.rpush(key, [json.dumps({"role": "user", "content": user_message})])

        # 2. Get conversation history (last 20 messages)
        history = await get_history(client, session_id, last_n=20)

        # 3. Call the LLM with full context
        bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "messages": history,  # ← directly from Valkey
            }),
        )
        assistant_msg = json.loads(response["body"].read())["content"][0]["text"]

        # 4. Save the assistant response
        await client.rpush(key, [json.dumps({"role": "assistant", "content": assistant_msg})])

        # 5. Refresh TTL
        await client.expire(key, 3600)

        return assistant_msg

    # --- Block 4 ---
    # Local Docker
    config = GlideClientConfiguration([NodeAddress("localhost", 6379)])

    # ElastiCache for Valkey
    config = GlideClientConfiguration(
        [NodeAddress("my-cluster.xxxxx.cache.amazonaws.com", 6379)],
        use_tls=True,
    )

