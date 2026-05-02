## LLM Cache Tier

The LLM cache stores full LLM responses by exact match on all parameters that affect the output.

### What Gets Hashed

The cache key is a SHA-256 hash of these fields (with recursively sorted dict keys for determinism):

| Field | Notes |
|-------|-------|
| `model` | `'gpt-4o'`, `'claude-opus-4-6'`, etc. |
| `messages` | Full message list including roles and content |
| `temperature` | `None` is treated as unset |
| `top_p` | `None` is treated as unset |
| `max_tokens` | `None` is treated as unset |
| `tools` | Tool definitions if present |
| `tool_choice` | `None` is treated as unset |
| `seed` | `None` is treated as unset |
| `stop` | `None` is treated as unset |
| `response_format` | `None` is treated as unset |
| `reasoning_effort` | For models supporting extended thinking |
| `prompt_cache_key` | Pass-through for provider-level prompt caching |

### Check and Store

```python
import valkey.asyncio as valkey_client
from openai import AsyncOpenAI
from betterdb_agent_cache import AgentCache, TierDefaults
from betterdb_agent_cache.types import AgentCacheOptions, LlmStoreOptions

client = valkey_client.Valkey(host="localhost", port=6379)
openai = AsyncOpenAI()

# cost_table is optional — 1,900+ models covered by default (see "Default Cost Table" below)
cache = AgentCache(AgentCacheOptions(
    client=client,
    tier_defaults={"llm": TierDefaults(ttl=3600)},
))

async def cached_completion(params: dict) -> str:
    cached = await cache.llm.check(params)
    if cached.hit:
        return cached.response or ""

    response = await openai.chat.completions.create(**params)
    text = response.choices[0].message.content or ""
    usage = response.usage

    await cache.llm.store(params, text, LlmStoreOptions(
        tokens={
            "input":  usage.prompt_tokens     if usage else 0,
            "output": usage.completion_tokens if usage else 0,
        },
    ))
    return text
```

Token counts in `store()` enable cost savings tracking via the cost table. Without `tokens`, cost tracking is skipped for that entry.

### Invalidating by Model

```python
deleted = await cache.llm.invalidate_by_model("gpt-4o-mini")
print(f"Deleted {deleted} entries")
```

---

## Tool Cache Tier

The tool cache stores tool/function call results. Valuable for expensive external API calls — weather, geocoding, database queries, web search — that return stable results for the same inputs.

### Check and Store

```python
import json
from betterdb_agent_cache.types import ToolStoreOptions

async def cached_tool(name: str, args: dict) -> dict:
    cached = await cache.tool.check(name, args)
    if cached.hit:
        return json.loads(cached.response)

    result = await call_tool(name, args)  # your tool implementation

    await cache.tool.store(name, args, json.dumps(result), ToolStoreOptions(
        ttl=300,    # per-call TTL override
        cost=0.005, # API call cost in dollars
    ))
    return result
```

### Per-Tool TTL Policies

```python
from betterdb_agent_cache.types import ToolPolicy

# Weather data: short TTL, changes frequently
await cache.tool.set_policy("get_weather",    ToolPolicy(ttl=300))    # 5 min

# Stock prices: very short TTL
await cache.tool.set_policy("get_stock_price", ToolPolicy(ttl=60))    # 1 min

# Geocoding: long TTL, addresses don't change
await cache.tool.set_policy("geocode_address", ToolPolicy(ttl=86400)) # 24h

# Web search: medium TTL
await cache.tool.set_policy("web_search",     ToolPolicy(ttl=3600))   # 1h
```

TTL precedence: per-call `ttl` > tool policy > `tier_defaults["tool"].ttl` > `default_ttl`.

### Invalidation

```python
# Invalidate all results for a specific tool
deleted = await cache.tool.invalidate_by_tool("get_weather")
print(f"Deleted {deleted} weather cache entries")

# Invalidate one specific call
existed = await cache.tool.invalidate("get_weather", {"city": "Sofia"})
```

---

## Cost Tracking and Stats

### Aggregate Stats

```python
stats = await cache.stats()
print(stats.llm.hits, stats.llm.misses, f"{stats.llm.hit_rate:.0%}")
# 150 50 75%

print(f"Cost saved: ${stats.cost_saved_micros / 1_000_000:.4f}")
# Cost saved: $12.5000

# Per-tool breakdown
for tool_name, tool_stats in stats.per_tool.items():
    print(f"{tool_name}: {tool_stats.hit_rate:.0%} hit rate")
```

Cost savings are stored as microdollars (integers) to avoid floating-point precision issues. Divide by `1_000_000` to get dollars.

### Tool Effectiveness Recommendations

```python
effectiveness = await cache.tool_effectiveness()
for entry in effectiveness:
    print(f"{entry.tool}: {entry.hit_rate:.0%} hit rate — {entry.recommendation}")
# get_weather:   85% hit rate — increase_ttl
# web_search:    62% hit rate — optimal
# rare_api_call:  8% hit rate — decrease_ttl_or_disable
```

| Recommendation | Condition | Action |
|---|---|---|
| `increase_ttl` | Hit rate > 80% and TTL < 1 hour | Results are stable and reused frequently — extend TTL |
| `optimal` | Hit rate 40–80% | No change needed |
| `decrease_ttl_or_disable` | Hit rate < 40% | Results change too fast or rarely repeated |

---

## Default Cost Table

`betterdb-agent-cache` ships a bundled cost table sourced from [LiteLLM's model pricing data](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) and refreshed on every release. Cost tracking works out of the box for 1,900+ models — no `cost_table` configuration required.

```python
# No cost_table needed — GPT-4o, Claude, Gemini, and 1,900+ others are covered
cache = AgentCache(AgentCacheOptions(client=client))
```

### Overriding Specific Models

User-supplied `cost_table` entries merge on top of the defaults:

```python
from betterdb_agent_cache import ModelCost

cache = AgentCache(AgentCacheOptions(
    client=client,
    cost_table={
        "my-fine-tuned-gpt4o": ModelCost(input_per_1k=0.005, output_per_1k=0.015),
    },
))
```

### Inspecting the Bundled Table

```python
from betterdb_agent_cache import DEFAULT_COST_TABLE

print(DEFAULT_COST_TABLE.get("gpt-4o-mini"))
# ModelCost(input_per_1k=0.00015, output_per_1k=0.0006)

print(len(DEFAULT_COST_TABLE))
# 1900+
```

### Disabling the Default Table

```python
cache = AgentCache(AgentCacheOptions(
    client=client,
    use_default_cost_table=False,
    cost_table={
        "gpt-4o": ModelCost(input_per_1k=0.0025, output_per_1k=0.010),
    },
))
```
