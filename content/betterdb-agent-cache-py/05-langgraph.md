`BetterDBSaver` is a LangGraph checkpoint saver backed by `betterdb-agent-cache`. It stores graph state on **vanilla Valkey 7+** with no modules required.

## Why BetterDBSaver vs langgraph-checkpoint-redis

| | `BetterDBSaver` | `langgraph-checkpoint-redis` |
|---|---|---|
| Valkey support | ✅ Valkey 7+ | ❌ Redis 8+ only |
| Module requirements | ✅ None | ❌ RedisJSON + RediSearch |
| Works on ElastiCache | ✅ Any tier | ❌ Requires Redis 8 + modules |
| Works on Memorystore | ✅ Any tier | ❌ Requires Redis 8 + modules |
| Checkpoint storage | Plain JSON strings | RedisJSON path operations |
| Filtered listing | SCAN + parse | O(1) RediSearch index |
| Async | ✅ Fully async | ✅ |
| Best for | Any Valkey/Redis deployment | Redis 8+ with modules, millions of checkpoints |

The trade-off: `alist()` with filtering uses SCAN. For typical deployments with hundreds of checkpoints per thread this is fast. `BetterDBSaver` is async-only — the sync `get_tuple()`, `list()`, and `put()` methods raise `RuntimeError`.

## Prerequisites

```bash
pip install "betterdb-agent-cache[langgraph]" langchain-openai
```

## Step 1: Create the Checkpointer

```python
import valkey.asyncio as valkey_client
from betterdb_agent_cache import AgentCache, TierDefaults
from betterdb_agent_cache.adapters.langgraph import BetterDBSaver
from betterdb_agent_cache.types import AgentCacheOptions

client = valkey_client.Valkey(host="localhost", port=6379)

cache = AgentCache(AgentCacheOptions(
    client=client,
    tier_defaults={
        "session": TierDefaults(ttl=86400),  # 24h session state
    },
))

checkpointer = BetterDBSaver(cache=cache)
```

## Step 2: Build a Graph with Checkpointing

```python
import json
import random
from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from betterdb_agent_cache.adapters.langchain import BetterDBLlmCache


class State(TypedDict):
    messages: Annotated[list, add_messages]


# Pass BetterDBLlmCache to LangChain so LLM responses are cached automatically
model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    cache=BetterDBLlmCache(cache=cache),
)

_TOOLS = [{"type": "function", "function": {
    "name": "get_weather",
    "description": "Get current weather for a city",
    "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
}}]
model_with_tools = model.bind_tools(_TOOLS)


async def get_weather(city: str) -> str:
    """Tool with its own cache tier."""
    cached = await cache.tool.check("get_weather", {"city": city})
    if cached.hit:
        return cached.response or ""
    result = json.dumps({
        "city": city,
        "temperature": round(15 + random.random() * 15),
        "condition": random.choice(["sunny", "cloudy", "rainy"]),
    })
    await cache.tool.store("get_weather", {"city": city}, result)
    return result


async def call_model(state: State) -> dict:
    response = await model_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}


async def call_tools(state: State) -> dict:
    last: AIMessage = state["messages"][-1]
    results = []
    for tc in getattr(last, "tool_calls", []) or []:
        if tc["name"] == "get_weather":
            result = await get_weather(tc["args"].get("city", ""))
            results.append(ToolMessage(content=result, tool_call_id=tc["id"]))
    return {"messages": results}


def should_continue(state: State) -> str:
    last: AIMessage = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END


graph = (
    StateGraph(State)
    .add_node("agent", call_model)
    .add_node("tools", call_tools)
    .add_edge("__start__", "agent")
    .add_conditional_edges("agent", should_continue)
    .add_edge("tools", "agent")
    .compile(checkpointer=checkpointer)  # attach BetterDBSaver here
)
```

## Step 3: Run the Graph Across Multiple Turns

```python
async def run_turn(thread_id: str, message: str) -> str:
    result = await graph.ainvoke(
        {"messages": [HumanMessage(message)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content


# First message — LangGraph stores the checkpoint in Valkey
r1 = await run_turn("user-42-thread-001", "What is the weather in Sofia?")
print(r1)
# "The weather in Sofia is 18°C and sunny."

# Second message — graph resumes from the Valkey checkpoint
r2 = await run_turn("user-42-thread-001", "And in Berlin?")
print(r2)
# "The weather in Berlin is 14°C and cloudy. Earlier you asked about Sofia (18°C, sunny)."
```

The graph has full conversation history because `BetterDBSaver` loaded the checkpoint from Valkey before the second invocation.

## Checkpoint Key Format

Checkpoints are stored as plain JSON strings in the session namespace:

```
betterdb_ac:session:{thread_id}:checkpoint:{checkpoint_id}
betterdb_ac:session:{thread_id}:__checkpoint_latest
betterdb_ac:session:{thread_id}:writes:{checkpoint_id}|{task_id}|{channel}|{idx}
```

They live under the session namespace so `destroy_thread(thread_id)` cleans up both session state and checkpoints in one call:

```python
await cache.session.destroy_thread("user-42-thread-001")
```

## Combined: LLM + Tool + Session + Checkpointing

All four capabilities from a single `AgentCache` instance:

```python
cache = AgentCache(AgentCacheOptions(
    client=client,
    tier_defaults={
        "llm":     TierDefaults(ttl=3600),
        "tool":    TierDefaults(ttl=300),
        "session": TierDefaults(ttl=86400),
    },
))

# LangGraph checkpointing
checkpointer = BetterDBSaver(cache=cache)

# LangChain LLM caching
model = ChatOpenAI(model="gpt-4o-mini", cache=BetterDBLlmCache(cache=cache))

# Tool caching: use cache.tool.check() / cache.tool.store() in tool nodes
# Session state: use cache.session.set() / get() for per-thread context

# When a conversation ends:
await cache.session.destroy_thread(thread_id)

# Monitor cost savings:
stats = await cache.stats()
print(f"Saved ${stats.cost_saved_micros / 1_000_000:.4f} so far")
```

> **Note:** `active_sessions` in Prometheus metrics is approximate — it uses an in-memory counter that resets on process restart.
