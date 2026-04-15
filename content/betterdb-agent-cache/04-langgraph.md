`BetterDBSaver` is a LangGraph checkpoint saver backed by `@betterdb/agent-cache`. It stores graph state on **vanilla Valkey 7+** with no modules required.

## Why BetterDBSaver vs langgraph-checkpoint-redis

| | `BetterDBSaver` | `langgraph-checkpoint-redis` |
|---|---|---|
| Valkey support | ✅ Valkey 7+ | ❌ Redis 8+ only |
| Module requirements | ✅ None | ❌ RedisJSON + RediSearch |
| Works on ElastiCache | ✅ Any tier | ❌ Requires Redis 8 + modules |
| Works on Memorystore | ✅ Any tier | ❌ Requires Redis 8 + modules |
| Checkpoint storage | Plain JSON strings | RedisJSON path operations |
| Filtered listing | SCAN + parse | O(1) RediSearch index |
| Best for | Any Valkey/Redis deployment | Redis 8+ with modules, millions of checkpoints |

The trade-off: `list()` with filtering is SCAN-based. For typical deployments with hundreds of checkpoints per thread this is fast. If you have millions of checkpoints per thread and need sub-millisecond filtered listing, use `langgraph-checkpoint-redis` with Redis 8 instead.

## Prerequisites

```bash
npm install @betterdb/agent-cache iovalkey @langchain/langgraph @langchain/openai
```

## Step 1: Create the Checkpointer

```typescript
import Valkey from 'iovalkey';
import { AgentCache } from '@betterdb/agent-cache';
import { BetterDBSaver } from '@betterdb/agent-cache/langgraph';

const client = new Valkey({ host: 'localhost', port: 6379 });

const cache = new AgentCache({
  client,
  tierDefaults: {
    session: { ttl: 86400 }, // 24h session state
  },
});

const checkpointer = new BetterDBSaver({ cache });
```

## Step 2: Build a Graph with Checkpointing

```typescript
import { StateGraph, MessagesAnnotation } from '@langchain/langgraph';
import { ChatOpenAI } from '@langchain/openai';
import { ToolNode } from '@langchain/langgraph/prebuilt';
import { tool } from '@langchain/core/tools';
import { z } from 'zod';

// Define a tool
const getWeather = tool(
  async ({ city }: { city: string }) => {
    // Check tool cache first
    const cached = await cache.tool.check('get_weather', { city });
    if (cached.hit) return cached.response!;

    const result = `${city}: 22°C, sunny`; // your real API call
    await cache.tool.store('get_weather', { city }, result, { ttl: 300 });
    return result;
  },
  {
    name: 'get_weather',
    description: 'Get current weather for a city',
    schema: z.object({ city: z.string() }),
  }
);

const model = new ChatOpenAI({ model: 'gpt-4o-mini' }).bindTools([getWeather]);

// Build the graph
const graph = new StateGraph(MessagesAnnotation)
  .addNode('agent', async (state) => {
    // Check LLM cache before calling the model
    const params = {
      model: 'gpt-4o-mini',
      messages: state.messages,
      temperature: 0,
    };

    const cached = await cache.llm.check(params);
    if (cached.hit) {
      return { messages: [{ role: 'assistant', content: cached.response! }] };
    }

    const response = await model.invoke(state.messages);

    await cache.llm.store(params, response.content as string);
    return { messages: [response] };
  })
  .addNode('tools', new ToolNode([getWeather]))
  .addEdge('__start__', 'agent')
  .addConditionalEdges('agent', (state) => {
    const last = state.messages.at(-1);
    if (last && 'tool_calls' in last && (last as any).tool_calls?.length) {
      return 'tools';
    }
    return '__end__';
  })
  .addEdge('tools', 'agent')
  .compile({ checkpointer }); // attach BetterDBSaver here
```

## Step 3: Run the Graph Across Multiple Turns

```typescript
const threadConfig = { configurable: { thread_id: 'user-42-thread-001' } };

// First message on this thread
const r1 = await graph.invoke(
  { messages: [{ role: 'user', content: 'What is the weather in Sofia?' }] },
  threadConfig
);
console.log(r1.messages.at(-1)?.content);
// "The weather in Sofia is 22°C and sunny."

// Second message - graph resumes from the checkpoint in Valkey
const r2 = await graph.invoke(
  { messages: [{ role: 'user', content: 'And in Berlin?' }] },
  threadConfig // same thread_id = same conversation
);
console.log(r2.messages.at(-1)?.content);
// "The weather in Berlin is 18°C and cloudy. Earlier you asked about Sofia (22°C, sunny)."
```

The graph has full conversation history because `BetterDBSaver` loaded the checkpoint from Valkey before the second invocation.

## Checkpoint Key Format

Checkpoints are stored as plain JSON strings:

```
betterdb_ac:session:{threadId}:checkpoint:{checkpointId}
betterdb_ac:session:{threadId}:__checkpoint_latest
betterdb_ac:session:{threadId}:writes:{checkpointId}|{taskId}|{channel}|{idx}
```

They live under the session namespace so `destroyThread(threadId)` cleans up both session state and checkpoints in one call.

## Combined: LLM + Tool + Session + Checkpointing

At full scale, all four capabilities work together from a single `AgentCache` instance:

```typescript
const cache = new AgentCache({
  client,
  costTable: { 'gpt-4o-mini': { inputPer1k: 0.00015, outputPer1k: 0.0006 } },
  tierDefaults: {
    llm:     { ttl: 3600  },
    tool:    { ttl: 300   },
    session: { ttl: 86400 },
  },
});

// LangGraph checkpointing
const checkpointer = new BetterDBSaver({ cache });
const graph = buildGraph({ checkpointer, cache });

// In your agent node: check cache.llm before calling the model
// In your tool nodes: check cache.tool before calling external APIs
// Session state: cache.session.set/get for per-thread context

// When a conversation ends:
await cache.session.destroyThread(threadId);

// Monitor cost savings:
const stats = await cache.stats();
console.log(`Saved $${(stats.costSavedMicros / 1_000_000).toFixed(4)} so far`);
```

> **Note:** `active_sessions` in Prometheus metrics is approximate - it uses an in-memory counter that resets on process restart. For exact session counts, use `SCAN betterdb_ac:session:*` directly.
