"""Integration tests for Conversation Memory - Session Management.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_02_session_management(client):
    """Run all code blocks from: Session Management."""

    # --- Block 1 ---
    import asyncio, json, time
    from glide import GlideClient, GlideClientConfiguration, NodeAddress


    async def create_session(client, session_id, user_id, model="claude-3-haiku"):
        meta_key = f"meta:{session_id}"
        await client.hset(meta_key, {
            "user_id": user_id,
            "model": model,
            "created_at": str(time.time()),
            "last_active": str(time.time()),
            "message_count": "0",
            "token_count": "0",
        })
        # Both keys expire together
        await client.expire(meta_key, 86400)  # 24 hours
        await client.expire(f"chat:{session_id}", 86400)

    # --- Block 2 ---
    async def add_message(client, session_id, role, content, tokens_used=0):
        chat_key = f"chat:{session_id}"
        meta_key = f"meta:{session_id}"

        # Append message to conversation
        await client.rpush(chat_key, [json.dumps({"role": role, "content": content})])

        # Update metadata atomically
        await client.hincrby(meta_key, "message_count", 1)
        await client.hincrby(meta_key, "token_count", tokens_used)
        await client.hset(meta_key, {"last_active": str(time.time())})

    # --- Block 3 ---
    async def add_message_windowed(client, session_id, role, content, max_messages=50):
        chat_key = f"chat:{session_id}"

        # Append
        await client.rpush(chat_key, [json.dumps({"role": role, "content": content})])

        # Trim to last N messages - O(1) for small trims
        await client.ltrim(chat_key, -max_messages, -1)

    # --- Block 4 ---
    async def list_user_sessions(client, user_id):
        """Find all active sessions for a user using SCAN."""
        sessions = []
        cursor = "0"
        while True:
            cursor, keys = await client.scan(cursor, match="meta:*", count=100)
            for key in keys:
                uid = await client.hget(key, "user_id")
                if uid and uid.decode() == user_id:
                    meta = await client.hgetall(key)
                    sessions.append({
                        k.decode(): v.decode() for k, v in meta.items()
                    })
            if cursor == 0:
                break
        return sessions

    # --- Block 5 ---
    async def get_session_info(client, session_id):
        meta = await client.hgetall(f"meta:{session_id}")
        msg_count = await client.llen(f"chat:{session_id}")
        ttl = await client.ttl(f"meta:{session_id}")

        return {
            "session_id": session_id,
            "metadata": {k.decode(): v.decode() for k, v in meta.items()},
            "messages_stored": msg_count,
            "expires_in_seconds": ttl,
        }

