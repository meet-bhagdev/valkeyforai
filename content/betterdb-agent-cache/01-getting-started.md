`@betterdb/agent-cache` is a multi-tier exact-match cache for AI agent workloads backed by Valkey. It combines three cache tiers behind one connection:

- **LLM tier** - caches full LLM responses by exact match on model + messages + params
- **Tool tier** - caches tool/function call results by tool name and argument hash
- **Session tier** - key-value store for agent state with per-field TTL

Unlike `langgraph-checkpoint-redis` or similar packages, it requires **no Valkey modules** - it works on vanilla Valkey 7+, Amazon ElastiCache, Google Cloud Memorystore, and Amazon MemoryDB with no configuration changes.

## Prerequisites

- **Valkey 7+** (no modules needed - no `valkey-search`, no RedisJSON)
- Or Amazon ElastiCache for Valkey / Redis, Google Cloud Memorystore, Amazon MemoryDB
- Node.js 20+

## Step 1: Start Valkey

No special image needed - the standard Valkey image works:

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install Packages

```bash
npm install @betterdb/agent-cache iovalkey
```

## Step 3: Create an AgentCache

```typescript
import Valkey from 'iovalkey';
import { AgentCache } from '@betterdb/agent-cache';

const client = new Valkey({ host: 'localhost', port: 6379 });

const cache = new AgentCache({
  client,
  tierDefaults: {
    llm:     { ttl: 3600  }, // LLM responses: 1 hour
    tool:    { ttl: 300   }, // Tool results: 5 minutes
    session: { ttl: 1800  }, // Session state: 30 minutes (sliding)
  },
  costTable: {
    'gpt-4o':      { inputPer1k: 0.0025, outputPer1k: 0.010 },
    'gpt-4o-mini': { inputPer1k: 0.00015, outputPer1k: 0.0006 },
  },
});
```

No `initialize()` call needed - all three tiers use plain Valkey commands (SET, GET, HINCRBY) with no index creation.

## Step 4: LLM Tier

```typescript
const params = {
  model: 'gpt-4o-mini',
  messages: [{ role: 'user', content: 'What is Valkey?' }],
  temperature: 0,
};

// Check for a cached response
const llmResult = await cache.llm.check(params);

if (llmResult.hit) {
  console.log('LLM cache HIT:', llmResult.response);
} else {
  console.log('LLM cache MISS → calling LLM...');
  const response = await callLlm(params); // your LLM call

  await cache.llm.store(params, response, {
    tokens: { input: 14, output: 62 }, // enables cost tracking
  });
}
```

The cache key is a SHA-256 hash of the canonicalized params (model, messages, temperature, top_p, max_tokens, tools). `{ messages: [...], model: 'gpt-4o' }` and `{ model: 'gpt-4o', messages: [...] }` produce the same key.

## Step 5: Tool Tier

```typescript
const toolName = 'get_weather';
const toolArgs = { city: 'Sofia', units: 'metric' };

const toolResult = await cache.tool.check(toolName, toolArgs);

if (toolResult.hit) {
  console.log('Tool cache HIT:', toolResult.response);
} else {
  console.log('Tool cache MISS → calling API...');
  const data = await getWeather(toolArgs); // your tool call

  await cache.tool.store(toolName, toolArgs, JSON.stringify(data), {
    cost: 0.001, // API call cost in dollars, for tracking
  });
}
```

Tool args are serialized with recursively sorted keys before hashing, so `{ city: 'Sofia', units: 'metric' }` and `{ units: 'metric', city: 'Sofia' }` hit the same cache entry.

## Step 6: Session Tier

```typescript
const threadId = 'user-42-session-1';

// Store agent state fields
await cache.session.set(threadId, 'last_intent', 'book_flight');
await cache.session.set(threadId, 'destination', 'Sofia');
await cache.session.set(threadId, 'departure_date', '2026-06-01');

// Retrieve a field
const intent = await cache.session.get(threadId, 'last_intent');
// 'book_flight'

// Get all fields for a thread
const state = await cache.session.getAll(threadId);
// { last_intent: 'book_flight', destination: 'Sofia', departure_date: '2026-06-01' }
```

Each `get()` refreshes the TTL on that field (sliding window). The session stays alive as long as the agent is actively using it.

## Key Formats

All keys are prefixed with the `name` option (default: `betterdb_ac`):

| Tier | Key Pattern |
|------|-------------|
| LLM cache | `betterdb_ac:llm:{sha256hash}` |
| Tool cache | `betterdb_ac:tool:{toolName}:{sha256hash}` |
| Session field | `betterdb_ac:session:{threadId}:{field}` |
| Stats hash | `betterdb_ac:stats` |

To use a separate namespace per environment or application:

```typescript
const cache = new AgentCache({
  client,
  name: 'myapp_prod', // all keys prefixed with 'myapp_prod:'
});
```

## Cleanup

```typescript
// Destroy all state for a thread (session + LangGraph checkpoints)
await cache.session.destroyThread(threadId);

// Invalidate all LLM cache entries for a model
await cache.llm.invalidateByModel('gpt-4o-mini');

// Close the client when done
await client.quit();
```
