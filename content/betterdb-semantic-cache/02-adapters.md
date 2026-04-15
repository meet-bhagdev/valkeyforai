Cookbook 01 showed the direct `check()` / `store()` API. For applications already using LangChain or the Vercel AI SDK, the package ships with first-class adapters that plug semantic caching in at the framework level - no manual hit/miss loops required.

## LangChain Adapter

`BetterDBSemanticCache` implements LangChain's `BaseCache` interface and is passed directly to any `ChatModel` or `LLM` constructor via the `cache` option.

### Setup

```typescript
import Valkey from 'iovalkey';
import { SemanticCache } from '@betterdb/semantic-cache';
import { BetterDBSemanticCache } from '@betterdb/semantic-cache/langchain';
import { ChatOpenAI } from '@langchain/openai';
import OpenAI from 'openai';

const openai = new OpenAI();
const client = new Valkey({ host: 'localhost', port: 6379 });

const cache = new SemanticCache({
  client,
  embedFn: async (text) => {
    const res = await openai.embeddings.create({
      model: 'text-embedding-3-small',
      input: text,
    });
    return res.data[0].embedding;
  },
  defaultThreshold: 0.15,
});

const model = new ChatOpenAI({
  model: 'gpt-4o-mini',
  cache: new BetterDBSemanticCache({ cache }),
});
```

### Usage

```typescript
import { HumanMessage } from '@langchain/core/messages';

// First call - miss, calls OpenAI
const r1 = await model.invoke([new HumanMessage('What is Valkey?')]);
console.log(r1.content);
// "Valkey is an open-source, in-memory data structure store..."

// Second call with different phrasing - hit, served from Valkey
const r2 = await model.invoke([new HumanMessage('Explain what Valkey is.')]);
console.log(r2.content);
// "Valkey is an open-source, in-memory data structure store..."  (same response, <1ms)

await client.quit();
```

### Scoping by Model

By default, cache entries are shared across all models. Set `filterByModel: true` to scope entries to the specific LLM configuration - useful when different models produce meaningfully different responses to the same prompt:

```typescript
const modelAwareCache = new BetterDBSemanticCache({
  cache,
  filterByModel: true, // a gpt-4o cache entry won't hit for gpt-4o-mini
});
```

---

## Vercel AI SDK Adapter

`createSemanticCacheMiddleware` wraps any Vercel AI SDK language model. Use it with `wrapLanguageModel()` from the `ai` package.

### Setup

```typescript
import Valkey from 'iovalkey';
import { SemanticCache } from '@betterdb/semantic-cache';
import { createSemanticCacheMiddleware } from '@betterdb/semantic-cache/ai';
import { wrapLanguageModel, generateText } from 'ai';
import { openai } from '@ai-sdk/openai';

const client = new Valkey({ host: 'localhost', port: 6379 });

const cache = new SemanticCache({
  client,
  embedFn: async (text) => {
    // same embed function as above
  },
  defaultThreshold: 0.15,
});

const model = wrapLanguageModel({
  model: openai('gpt-4o-mini'),
  middleware: createSemanticCacheMiddleware({ cache }),
});
```

### Usage

```typescript
// First call - miss
const { text: t1 } = await generateText({
  model,
  prompt: 'What is Valkey?',
});
console.log(t1);

// Second call - hit, returned from Valkey, no tokens consumed
const { text: t2 } = await generateText({
  model,
  prompt: 'Can you describe what Valkey is?',
});
console.log(t2); // same response as t1

await client.quit();
```

The middleware intercepts `doGenerate()` calls before they reach OpenAI. On a hit it returns the cached response directly - no API call, no tokens, no latency.

> **Streaming:** The Vercel AI SDK adapter caches `generateText()` calls only. Streaming responses via `streamText()` are not cached - accumulate the full response and call `cache.store()` manually if you need to cache streamed output.

---

## Direct API vs Adapters

| | Direct API | LangChain Adapter | Vercel AI SDK Adapter |
|---|---|---|---|
| Framework dependency | None | `@langchain/core` | `ai` package |
| `check()` / `store()` control | Full | Automatic | Automatic |
| Works with any LLM client | Yes | LangChain models only | Vercel AI models only |
| Streaming support | Manual | Automatic (no cache) | No (generateText only) |
| Best for | Custom pipelines | LangChain agents | Next.js / AI SDK apps |

Use the direct API when you need fine-grained control - for example, to pass per-request TTLs, categories, or to handle uncertain hits differently. Use an adapter when you want zero-boilerplate caching for an existing LangChain or Vercel AI SDK application.
