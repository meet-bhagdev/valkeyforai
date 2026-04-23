Provider adapters translate the native params of each SDK into the canonical `LlmCacheParams` format before hashing. The pattern is the same across all four adapters:

1. Call `prepareParams()` on the native SDK params
2. Pass the result to `cache.llm.check()`
3. On a miss, call the provider and build `ContentBlock[]` from the response
4. Store with `cache.llm.storeMultipart()` — this handles text, tool calls, and reasoning blocks together

All four adapters support multi-modal content (images, audio, documents) and use the same pluggable binary normalizer for stable hashing.

## Binary Normalizer

The binary normalizer controls how binary content — images, audio, documents — is reduced to a stable string before being included in the cache key hash.

The **default** is `passthrough`: the full base64 data string is included literally. This is zero-latency and correct, but means a re-encoded image byte-for-byte identical in content but with different base64 padding will produce a different hash.

For production use, switch to `hashBase64` to hash the decoded bytes instead:

```typescript
import { composeNormalizer, hashBase64 } from '@betterdb/agent-cache';

// Hash base64 image/audio/document bytes — O(n) in content size, no network calls
const normalizer = composeNormalizer({ base64: hashBase64 });
```

Other built-in helpers:

| Helper | Behavior |
|--------|----------|
| `hashBase64(data)` | SHA-256 of decoded bytes — stable across re-encodings |
| `hashBytes(buf)` | SHA-256 of a `Buffer` or `Uint8Array` |
| `hashUrl(url)` | Lowercases scheme+host, sorts query params, returns `"url:<normalized>"` |
| `fetchAndHash(url)` | Fetches the URL and returns SHA-256 of the body — most stable, adds latency |
| `passthrough(ref)` | Returns the raw data as-is (default) |

For per-kind control:

```typescript
import { composeNormalizer, hashBase64, fetchAndHash } from '@betterdb/agent-cache';

const normalizer = composeNormalizer({
  base64: hashBase64,           // Hash inline images/audio
  byKind: {
    document: async (ref) => {  // Fetch and hash remote documents
      if (ref.source.type === 'url') return fetchAndHash(ref.source.url);
      return hashBase64((ref.source as { data: string }).data);
    },
  },
});
```

---

## OpenAI Chat Completions

```bash
npm install @betterdb/agent-cache openai iovalkey
```

```typescript
import Valkey from 'iovalkey';
import OpenAI from 'openai';
import { AgentCache, composeNormalizer, hashBase64 } from '@betterdb/agent-cache';
import { prepareParams } from '@betterdb/agent-cache/openai';
import type { ContentBlock, TextBlock, ToolCallBlock } from '@betterdb/agent-cache';
import type { ChatCompletionCreateParamsNonStreaming } from 'openai/resources/chat/completions';

const valkey = new Valkey({ host: 'localhost', port: 6379 });
const cache = new AgentCache({ client: valkey, tierDefaults: { llm: { ttl: 3600 } } });
const normalizer = composeNormalizer({ base64: hashBase64 });
const openai = new OpenAI();

async function chat(params: ChatCompletionCreateParamsNonStreaming): Promise<string> {
  // Translate OpenAI params → canonical LlmCacheParams
  const cacheParams = await prepareParams(params, { normalizer });

  const cached = await cache.llm.check(cacheParams);
  if (cached.hit) return cached.response ?? '';

  const response = await openai.chat.completions.create({ ...params, stream: false });
  const choice = response.choices[0];

  // Build content blocks — text and tool calls both need to be stored
  const blocks: ContentBlock[] = [];
  if (choice.message.content) {
    blocks.push({ type: 'text', text: choice.message.content } as TextBlock);
  }
  if (choice.message.tool_calls) {
    for (const tc of choice.message.tool_calls) {
      let args: unknown;
      try { args = JSON.parse(tc.function.arguments || '{}'); } catch { args = { __raw: tc.function.arguments }; }
      blocks.push({ type: 'tool_call', id: tc.id, name: tc.function.name, args } as ToolCallBlock);
    }
  }

  await cache.llm.storeMultipart(cacheParams, blocks, {
    tokens: {
      input: response.usage?.prompt_tokens ?? 0,
      output: response.usage?.completion_tokens ?? 0,
    },
  });

  const textBlocks = blocks.filter((b): b is TextBlock => b.type === 'text');
  return textBlocks.map(b => b.text).join('');
}
```

`prepareParams` handles all message roles: `system`, `developer`, `user`, `assistant`, `tool`, and legacy `function`. Multi-modal user messages (images, audio, file uploads) are normalized through the binary normalizer before hashing.

### What Gets Hashed (OpenAI Chat)

In addition to the base fields, `prepareParams` also maps these OpenAI params into the cache key:

| OpenAI param | `LlmCacheParams` field |
|---|---|
| `tool_choice` | `toolChoice` |
| `seed` | `seed` |
| `stop` | `stop` |
| `response_format` | `responseFormat` |
| `prompt_cache_key` | `promptCacheKey` |

---

## OpenAI Responses API

```bash
npm install @betterdb/agent-cache openai iovalkey
```

```typescript
import Valkey from 'iovalkey';
import OpenAI from 'openai';
import { AgentCache, composeNormalizer, hashBase64 } from '@betterdb/agent-cache';
import { prepareParams } from '@betterdb/agent-cache/openai-responses';
import type { ContentBlock, TextBlock, ToolCallBlock, ReasoningBlock } from '@betterdb/agent-cache';
import type { ResponseCreateParams } from 'openai/resources/responses/responses';

const valkey = new Valkey({ host: 'localhost', port: 6379 });
const cache = new AgentCache({ client: valkey, tierDefaults: { llm: { ttl: 3600 } } });
const normalizer = composeNormalizer({ base64: hashBase64 });
const openai = new OpenAI();

async function respond(params: ResponseCreateParams): Promise<string> {
  const cacheParams = await prepareParams(params, { normalizer });

  const cached = await cache.llm.check(cacheParams);
  if (cached.hit) return cached.response ?? '';

  const response = await openai.responses.create(params);

  const blocks: ContentBlock[] = [];
  for (const item of response.output ?? []) {
    if (item.type === 'message') {
      for (const part of item.content ?? []) {
        if (part.type === 'output_text') blocks.push({ type: 'text', text: part.text } as TextBlock);
      }
    } else if (item.type === 'reasoning') {
      const text = (item.summary ?? []).filter((s: { type?: string }) => s.type === 'reasoning_text').map((s: { text: string }) => s.text).join('');
      blocks.push({ type: 'reasoning', text } as ReasoningBlock);
    } else if (item.type === 'function_call') {
      let args: unknown;
      try { args = JSON.parse(item.arguments || '{}'); } catch { args = { __raw: item.arguments }; }
      blocks.push({ type: 'tool_call', id: item.call_id, name: item.name, args } as ToolCallBlock);
    }
  }

  await cache.llm.storeMultipart(cacheParams, blocks, {
    tokens: {
      input: response.usage?.input_tokens ?? 0,
      output: response.usage?.output_tokens ?? 0,
    },
  });

  const textBlocks = blocks.filter((b): b is TextBlock => b.type === 'text');
  return textBlocks.map(b => b.text).join('');
}
```

`instructions` is prepended as a `system` message in the canonical format. The adapter handles `reasoning` items (extended thinking), `function_call` / `function_call_output` item types, and multi-modal `input_image` / `input_file` parts. `reasoning.effort` maps to `reasoningEffort` in the cache key.

---

## Anthropic Messages

```bash
npm install @betterdb/agent-cache @anthropic-ai/sdk iovalkey
```

```typescript
import Valkey from 'iovalkey';
import Anthropic from '@anthropic-ai/sdk';
import { AgentCache, composeNormalizer, hashBase64 } from '@betterdb/agent-cache';
import { prepareParams } from '@betterdb/agent-cache/anthropic';
import type { ContentBlock, TextBlock, ToolCallBlock, ReasoningBlock } from '@betterdb/agent-cache';
import type { MessageCreateParamsNonStreaming } from '@anthropic-ai/sdk/resources';

const valkey = new Valkey({ host: 'localhost', port: 6379 });
const cache = new AgentCache({ client: valkey, tierDefaults: { llm: { ttl: 3600 } } });
const normalizer = composeNormalizer({ base64: hashBase64 });
const anthropic = new Anthropic();

async function chat(params: MessageCreateParamsNonStreaming): Promise<string> {
  const cacheParams = await prepareParams(params, { normalizer });

  const cached = await cache.llm.check(cacheParams);
  if (cached.hit) return cached.response ?? '';

  const response = await anthropic.messages.create(params);

  const blocks: ContentBlock[] = [];
  for (const block of response.content) {
    if (block.type === 'text') {
      blocks.push({ type: 'text', text: block.text } as TextBlock);
    } else if (block.type === 'tool_use') {
      blocks.push({ type: 'tool_call', id: block.id, name: block.name, args: block.input } as ToolCallBlock);
    } else if (block.type === 'thinking') {
      blocks.push({ type: 'reasoning', text: block.thinking } as ReasoningBlock);
    }
  }

  await cache.llm.storeMultipart(cacheParams, blocks, {
    tokens: {
      input: response.usage.input_tokens,
      output: response.usage.output_tokens,
    },
  });

  const textBlocks = blocks.filter((b): b is TextBlock => b.type === 'text');
  return textBlocks.map(b => b.text).join('');
}
```

`params.system` is prepended as a `system` message. `tool_result` blocks in user messages are split into separate `tool` messages in the canonical format. `thinking` and `redacted_thinking` blocks map to `ReasoningBlock`. `stop_sequences` maps to `stop` in the cache key.

---

## LlamaIndex

```bash
npm install @betterdb/agent-cache @llamaindex/core @llamaindex/openai iovalkey
```

```typescript
import Valkey from 'iovalkey';
import { OpenAI } from '@llamaindex/openai';
import { AgentCache, composeNormalizer, hashBase64 } from '@betterdb/agent-cache';
import { prepareParams } from '@betterdb/agent-cache/llamaindex';
import type { ContentBlock, TextBlock } from '@betterdb/agent-cache';
import type { ChatMessage } from '@llamaindex/core/llms';

const valkey = new Valkey({ host: 'localhost', port: 6379 });
const cache = new AgentCache({ client: valkey, tierDefaults: { llm: { ttl: 3600 } } });
const normalizer = composeNormalizer({ base64: hashBase64 });
const llm = new OpenAI({ model: 'gpt-4o-mini' });

async function chat(messages: ChatMessage[]): Promise<string> {
  // model must be supplied explicitly — LlamaIndex messages don't carry it
  const cacheParams = await prepareParams(messages, {
    model: 'gpt-4o-mini',
    normalizer,
    temperature: 0,
  });

  const cached = await cache.llm.check(cacheParams);
  if (cached.hit) return cached.response ?? '';

  const response = await llm.chat({ messages });
  const text = response.message.content as string;

  const blocks: ContentBlock[] = [{ type: 'text', text } as TextBlock];
  const usage = (response.raw as { usage?: { prompt_tokens?: number; completion_tokens?: number } } | null)?.usage;

  await cache.llm.storeMultipart(cacheParams, blocks, {
    tokens: {
      input: usage?.prompt_tokens ?? 0,
      output: usage?.completion_tokens ?? 0,
    },
  });

  return text;
}
```

The LlamaIndex adapter differs from the others in that the model name is not available from `ChatMessage` objects — you supply it via `opts.model`. The `memory` and `developer` roles are mapped to `system`. Tool calls are read from `message.options.toolCall` and tool results from `message.options.toolResult`.

---

## Adapter Import Paths

| Provider | Import path |
|---|---|
| OpenAI Chat Completions | `@betterdb/agent-cache/openai` |
| OpenAI Responses API | `@betterdb/agent-cache/openai-responses` |
| Anthropic Messages | `@betterdb/agent-cache/anthropic` |
| LlamaIndex | `@betterdb/agent-cache/llamaindex` |
| LangChain | `@betterdb/agent-cache/langchain` |
| Vercel AI SDK | `@betterdb/agent-cache/ai` |
| LangGraph | `@betterdb/agent-cache/langgraph` |
