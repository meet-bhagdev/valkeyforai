`@betterdb/semantic-cache` is a standalone semantic cache for LLM applications backed by Valkey. It uses the `valkey-search` module for vector similarity matching so semantically similar prompts - "What is Valkey?" and "Can you explain Valkey?" - return the same cached response without calling the LLM again.

Unlike other semantic cache libraries it is **Valkey-native** (handles `valkey-search` API differences from Redis), **standalone** (no LangChain or LiteLLM dependency), and ships with **built-in OpenTelemetry tracing and Prometheus metrics** at the cache-operation level, not just at the HTTP level.

## Prerequisites

- Valkey 8.0+ with the `valkey-search` module, or Amazon ElastiCache for Valkey 8.0+, or Google Cloud Memorystore for Valkey
- Node.js 20+
- An embedding provider (OpenAI, Voyage AI, Cohere, or any `(text: string) => Promise<number[]>` function)

## Step 1: Start Valkey

The `valkey-bundle` image includes the `valkey-search` module required for vector indexing.

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

Verify the module is loaded:

```bash
docker exec valkey valkey-cli MODULE LIST
# Should include "search"
```

## Step 2: Install Packages

```bash
npm install @betterdb/semantic-cache iovalkey
```

`iovalkey` is a peer dependency - it is the client library used to communicate with Valkey.

## Step 3: Write an Embedding Function

The cache accepts any function with the signature `(text: string) => Promise<number[]>`. Here is an example using OpenAI:

```typescript
import OpenAI from 'openai';

const openai = new OpenAI(); // reads OPENAI_API_KEY from env

async function embedFn(text: string): Promise<number[]> {
  const res = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text,
  });
  return res.data[0].embedding; // 1536-dimensional vector
}
```

Any provider works. Voyage AI, Cohere, AWS Bedrock Titan, and local models served over HTTP all work as long as they return a `number[]`.

## Step 4: Initialize the Cache

```typescript
import Valkey from 'iovalkey';
import { SemanticCache } from '@betterdb/semantic-cache';

const client = new Valkey({ host: 'localhost', port: 6379 });

const cache = new SemanticCache({
  client,
  embedFn,
  defaultThreshold: 0.15, // cosine distance - see Step 6
  defaultTtl: 3600,        // entries expire after 1 hour
});

await cache.initialize(); // creates the Valkey search index
```

`initialize()` is safe to call on every startup - it is a no-op if the index already exists.

## Step 5: Store and Check

```typescript
import OpenAI from 'openai';

const llm = new OpenAI();

async function ask(prompt: string): Promise<string> {
  // 1. Check for a semantically similar cached prompt
  const cached = await cache.check(prompt);

  if (cached.hit) {
    console.log(`Cache HIT  (score ${cached.similarity?.toFixed(4)})`);
    return cached.response!;
  }

  // 2. Miss - call the LLM
  console.log('Cache MISS → calling LLM...');
  const completion = await llm.chat.completions.create({
    model: 'gpt-4o-mini',
    messages: [{ role: 'user', content: prompt }],
  });
  const response = completion.choices[0].message.content!;

  // 3. Store so future similar prompts are served from cache
  await cache.store(prompt, response);
  return response;
}

// First call: miss, calls LLM, stores result
await ask('What is Valkey?');

// Second call: hit, returned from cache
await ask('Can you explain what Valkey is?');

await client.quit();
```

Expected output:

```
Cache MISS → calling LLM...
Cache HIT  (score 0.0821)
```

The second prompt has a cosine distance of ~0.08 from the first - well below the 0.15 threshold - so it is served from cache.

## Step 6: Understanding the Threshold

`defaultThreshold` is a **cosine distance** on the 0–2 scale, not the 0–1 cosine similarity scale. A hit occurs when `score <= threshold`.

| Distance | Meaning | Recommendation |
|----------|---------|---------------|
| `0.05` | Near-identical phrasing | Medical, legal, financial |
| `0.10` | Very similar (package default) | Strict quality requirements |
| `0.15–0.20` | Balanced | General chatbots - start here |
| `0.30+` | Broad matching | FAQ bots with high hit-rate goal |

> **Tip:** Start at `0.15` and tune based on observed hit rates and false-positive rates. Cookbook 03 covers threshold tuning in detail.

## Step 7: Inspect Stats

```typescript
const stats = await cache.stats();
console.log(stats);
// { hits: 3, misses: 2, total: 5, hitRate: 0.6 }
```

Stats are stored as atomic counters in Valkey - they persist across restarts and accumulate across all processes sharing the same instance.

```typescript
const info = await cache.indexInfo();
console.log(info);
// { name: 'betterdb_scache', numDocs: 48, dimension: 1536, indexingState: 'ready' }
```
