## LLM Cache Tier

The LLM cache stores full LLM responses by exact match on all parameters that affect the output.

### What Gets Hashed

The cache key is a SHA-256 hash of these fields (with recursively sorted object keys for determinism):

| Field | Notes |
|-------|-------|
| `model` | `'gpt-4o'`, `'gpt-4o-mini'`, etc. |
| `messages` | Full message array including roles and content |
| `temperature` | `undefined` is treated as unset |
| `top_p` | `undefined` is treated as unset |
| `max_tokens` | `undefined` is treated as unset |
| `tools` | Tool definitions if present |

Changing any of these fields produces a different cache key. This means a prompt cached at `temperature: 0` will not hit at `temperature: 0.7`.

### Check and Store

```typescript
import Valkey from 'iovalkey';
import { AgentCache } from '@betterdb/agent-cache';
import OpenAI from 'openai';

const client = new Valkey({ host: 'localhost', port: 6379 });
const openai = new OpenAI();

const cache = new AgentCache({
  client,
  tierDefaults: { llm: { ttl: 3600 } },
  costTable: {
    'gpt-4o-mini': { inputPer1k: 0.00015, outputPer1k: 0.0006 },
  },
});

async function cachedCompletion(params: {
  model: string;
  messages: Array<{ role: string; content: string }>;
  temperature: number;
}) {
  const cached = await cache.llm.check(params);
  if (cached.hit) {
    return cached.response!;
  }

  const completion = await openai.chat.completions.create(params);
  const response = completion.choices[0].message.content!;
  const usage = completion.usage!;

  await cache.llm.store(params, response, {
    tokens: {
      input: usage.prompt_tokens,
      output: usage.completion_tokens,
    },
  });

  return response;
}
```

Token counts in `store()` enable cost savings tracking via the `costTable`. Without `tokens`, cost tracking is skipped for that entry.

### Invalidating by Model

When you change a model's system prompt or want to force fresh responses after fine-tuning:

```typescript
const deleted = await cache.llm.invalidateByModel('gpt-4o-mini');
console.log(`Deleted ${deleted} entries`);
```

This uses SCAN to find and delete all entries with `betterdb_ac:llm:*` that match the model. Use `name` prefix isolation if you want per-environment invalidation without touching other environments.

---

## Tool Cache Tier

The tool cache stores tool/function call results. It is especially valuable for expensive external API calls - weather, geocoding, database queries, web search - that return stable results for the same inputs.

### Check and Store

```typescript
async function cachedTool(name: string, args: Record<string, unknown>) {
  const cached = await cache.tool.check(name, args);
  if (cached.hit) {
    return JSON.parse(cached.response!);
  }

  const result = await callTool(name, args); // your tool implementation

  await cache.tool.store(name, args, JSON.stringify(result), {
    ttl: 300,     // per-call TTL override
    cost: 0.005,  // API call cost in dollars
  });

  return result;
}
```

### Per-Tool TTL Policies

Different tools have different data freshness requirements. Use `setPolicy()` to configure per-tool defaults:

```typescript
// Weather data: short TTL, changes frequently
await cache.tool.setPolicy('get_weather', { ttl: 300 }); // 5 min

// Stock prices: very short TTL
await cache.tool.setPolicy('get_stock_price', { ttl: 60 }); // 1 min

// Geocoding: long TTL, addresses don't change
await cache.tool.setPolicy('geocode_address', { ttl: 86400 }); // 24h

// Web search results: medium TTL
await cache.tool.setPolicy('web_search', { ttl: 3600 }); // 1h
```

TTL precedence: per-call `ttl` > tool policy > `tierDefaults.tool.ttl` > `defaultTtl`.

### Invalidation

```typescript
// Invalidate all results for a specific tool
const deleted = await cache.tool.invalidateByTool('get_weather');
console.log(`Deleted ${deleted} weather cache entries`);

// Invalidate one specific call
const existed = await cache.tool.invalidate('get_weather', { city: 'Sofia' });
```

---

## Cost Tracking and Stats

### Aggregate Stats

```typescript
const stats = await cache.stats();
console.log(stats);
/*
{
  llm:  { hits: 150, misses: 50, total: 200, hitRate: 0.75 },
  tool: { hits: 300, misses: 100, total: 400, hitRate: 0.75 },
  session: { reads: 1000, writes: 500 },
  costSavedMicros: 12500000,  // $12.50 - stored as microdollars to avoid float precision issues
  perTool: {
    get_weather: { hits: 200, misses: 50, hitRate: 0.80, ttl: 300 },
    web_search:  { hits: 100, misses: 50, hitRate: 0.67, ttl: 3600 },
  }
}
*/

// Convert microdollars to dollars
const costSaved = stats.costSavedMicros / 1_000_000;
console.log(`Cost saved: $${costSaved.toFixed(4)}`);
```

### Tool Effectiveness Recommendations

`toolEffectiveness()` returns per-tool hit rates and recommendations based on observed behavior:

```typescript
const effectiveness = await cache.toolEffectiveness();
console.log(effectiveness);
/*
[
  { tool: 'get_weather',   hitRate: 0.85, costSaved: 5.00, recommendation: 'increase_ttl' },
  { tool: 'web_search',    hitRate: 0.62, costSaved: 2.50, recommendation: 'optimal' },
  { tool: 'rare_api_call', hitRate: 0.08, costSaved: 0.10, recommendation: 'decrease_ttl_or_disable' },
]
*/
```

| Recommendation | Condition | Action |
|---------------|-----------|--------|
| `increase_ttl` | Hit rate > 80% and TTL < 1 hour | Extend TTL - results are stable and reused frequently |
| `optimal` | Hit rate 40–80% | No change needed |
| `decrease_ttl_or_disable` | Hit rate < 40% | Results change too fast or are rarely repeated - consider disabling cache for this tool |
