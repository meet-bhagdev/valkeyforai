"""Integration tests for Conversation Memory - Agent State.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_05_agent_state(client):
    """Run all code blocks from: Agent State."""

    # --- Block 1 ---
    import json
    from glide import GlideClient, GlideClientConfiguration, NodeAddress

    async def save_checkpoint(client, run_id, step, data):
        """Save agent state after completing a step."""
        key = f"agent:state:{run_id}"
        await client.hset(key, {
            "current_step": str(step),
            "status": "in_progress",
            f"result_step_{step}": json.dumps(data),
            "updated_at": str(time.time()),
        })
        await client.expire(key, 86400)  # 24h TTL


    async def load_checkpoint(client, run_id):
        """Load the last checkpoint to resume."""
        key = f"agent:state:{run_id}"
        state = await client.hgetall(key)
        if not state:
            return None
        return {k.decode(): v.decode() for k, v in state.items()}


    async def mark_complete(client, run_id):
        await client.hset(f"agent:state:{run_id}", {"status": "complete"})

    # --- Block 2 ---
    import hashlib

    async def cached_tool_call(client, tool_name, args, tool_fn, ttl=300):
        """Call a tool, caching the result in Valkey."""
        # Create a cache key from tool name + arguments
        args_hash = hashlib.md5(json.dumps(args, sort_keys=True).encode()).hexdigest()[:12]
        cache_key = f"tool:cache:{tool_name}:{args_hash}"

        # Check cache first
        cached = await client.get(cache_key)
        if cached:
            print(f"⚡ Tool cache HIT: {tool_name}")
            return json.loads(cached)

        # Cache miss - call the tool
        print(f"🔄 Tool cache MISS: {tool_name} - calling...")
        result = tool_fn(**args)

        # Store with TTL
        await client.set(cache_key, json.dumps(result))
        await client.expire(cache_key, ttl)

        return result


    # Usage
    result = await cached_tool_call(
        client, "web_search",
        {"query": "Valkey vector search benchmarks"},
        tool_fn=web_search,
        ttl=600,  # cache for 10 minutes
    )

    # --- Block 3 ---
    async def log_action(client, run_id, action, details):
        """Append an action to the agent's activity log."""
        stream_key = f"agent:log:{run_id}"
        await client.xadd(stream_key, [
            ("action", action),
            ("details", json.dumps(details)),
            ("ts", str(time.time())),
        ])


    async def get_action_log(client, run_id):
        """Read the full activity log for a run."""
        from glide import StreamReadOptions
        stream_key = f"agent:log:{run_id}"
        result = await client.xread({stream_key: "0"}, StreamReadOptions(count=1000))
        if not result:
            return []

        entries = []
        for key, events in result.items():
            for entry_id, fields in events.items():
                entry = {k.decode(): v.decode() for k, v in fields}
                entry["id"] = entry_id.decode()
                entries.append(entry)
        return entries

    # --- Block 4 ---
    async def run_agent(client, run_id, query):
        # Check for existing checkpoint
        checkpoint = await load_checkpoint(client, run_id)
        start_step = int(checkpoint["current_step"]) + 1 if checkpoint else 1

        if start_step > 1:
            print(f"♻️  Resuming from step {start_step}")

        # Step 1: Search
        if start_step <= 1:
            await log_action(client, run_id, "search", {"query": query})
            results = await cached_tool_call(
                client, "web_search", {"query": query}, web_search)
            await save_checkpoint(client, run_id, 1, {"search_results": results})

        # Step 2: Analyze
        if start_step <= 2:
            await log_action(client, run_id, "analyze", {"input": "search results"})
            analysis = call_llm(f"Analyze: {results}")
            await save_checkpoint(client, run_id, 2, {"analysis": analysis})

        # Step 3: Respond
        if start_step <= 3:
            await log_action(client, run_id, "respond", {"status": "generating"})
            response = call_llm(f"Respond based on: {analysis}")
            await save_checkpoint(client, run_id, 3, {"response": response})

        await mark_complete(client, run_id)
        await log_action(client, run_id, "complete", {"status": "done"})
        return response

    # --- Block 5 ---
    log = await get_action_log(client, "run_001")
    for entry in log:
        print(f"  [{entry['id']}] {entry['action']}: {entry['details']}")

    # Output:
    # [1710000000001-0] search: {"query": "Valkey benchmarks"}
    # [1710000000002-0] analyze: {"input": "search results"}
    # [1710000000003-0] respond: {"status": "generating"}
    # [1710000000004-0] complete: {"status": "done"}

