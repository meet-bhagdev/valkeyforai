Provider adapters translate the native params of each SDK into the canonical `LlmCacheParams` format before hashing. The pattern is the same across all four adapters:

1. Call `prepare_params()` on the native SDK params dict
2. Pass the result to `cache.llm.check()`
3. On a miss, call the provider and build a list of content block dicts from the response
4. Store with `cache.llm.store_multipart()` — handles text, tool calls, and reasoning blocks together

## Binary Normalizer

The binary normalizer controls how binary content — images, audio, documents — is reduced to a stable string before being included in the cache key hash.

The **default** is `passthrough`: the full base64 data string is included literally. Zero-latency and correct, but a re-encoded image that is byte-for-byte identical but with different base64 padding will produce a different hash.

For production use, switch to `hash_base64`:

```python
from betterdb_agent_cache import compose_normalizer, hash_base64

# Hash base64 image/audio/document bytes — O(n) in content size, no network calls
normalizer = compose_normalizer({"base64": hash_base64})
```

Other built-in helpers:

| Helper | Behavior |
|--------|----------|
| `hash_base64(data)` | SHA-256 of decoded bytes — stable across re-encodings |
| `hash_bytes(data)` | SHA-256 of raw `bytes` |
| `hash_url(url)` | Lowercases scheme+host, sorts query params, returns `"url:<normalised>"` |
| `fetch_and_hash(url)` | Fetches the URL (requires `aiohttp`) and returns SHA-256 of the body |
| `passthrough(ref)` | Returns the raw data as-is (default) |

---

## OpenAI Chat Completions

```bash
pip install "betterdb-agent-cache[openai]"
```

```python
import json
import valkey.asyncio as valkey_client
from openai import AsyncOpenAI
from betterdb_agent_cache import AgentCache, TierDefaults, compose_normalizer, hash_base64
from betterdb_agent_cache.adapters.openai import OpenAIPrepareOptions, prepare_params
from betterdb_agent_cache.types import AgentCacheOptions, LlmStoreOptions

client = valkey_client.Valkey(host="localhost", port=6379)
cache = AgentCache(AgentCacheOptions(
    client=client,
    tier_defaults={"llm": TierDefaults(ttl=3600)},
))
normalizer = compose_normalizer({"base64": hash_base64})
opts = OpenAIPrepareOptions(normalizer=normalizer)
openai = AsyncOpenAI()

async def chat(params: dict) -> str:
    # Translate OpenAI params → canonical LlmCacheParams
    cache_params = await prepare_params(params, opts)

    cached = await cache.llm.check(cache_params)
    if cached.hit:
        return cached.response or ""

    response = await openai.chat.completions.create(**params, stream=False)
    choice = response.choices[0]

    blocks = []
    if choice.message.content:
        blocks.append({"type": "text", "text": choice.message.content})
    for tc in choice.message.tool_calls or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {"__raw": tc.function.arguments}
        blocks.append({"type": "tool_call", "id": tc.id, "name": tc.function.name, "args": args})

    await cache.llm.store_multipart(cache_params, blocks, LlmStoreOptions(tokens={
        "input":  response.usage.prompt_tokens     if response.usage else 0,
        "output": response.usage.completion_tokens if response.usage else 0,
    }))

    return " ".join(b["text"] for b in blocks if b.get("type") == "text")
```

`prepare_params` handles all message roles: `system`, `developer`, `user`, `assistant`, `tool`, and legacy `function`. Multi-modal user messages (images, audio, file uploads) are normalized through the binary normalizer before hashing.

---

## OpenAI Responses API

```bash
pip install "betterdb-agent-cache[openai]"
```

```python
import valkey.asyncio as valkey_client
from openai import AsyncOpenAI
from betterdb_agent_cache import AgentCache, TierDefaults, compose_normalizer, hash_base64
from betterdb_agent_cache.adapters.openai_responses import OpenAIResponsesPrepareOptions, prepare_params
from betterdb_agent_cache.types import AgentCacheOptions, LlmStoreOptions

client = valkey_client.Valkey(host="localhost", port=6379)
cache = AgentCache(AgentCacheOptions(
    client=client,
    tier_defaults={"llm": TierDefaults(ttl=3600)},
))
normalizer = compose_normalizer({"base64": hash_base64})
opts = OpenAIResponsesPrepareOptions(normalizer=normalizer)
openai = AsyncOpenAI()

async def respond(params: dict) -> str:
    cache_params = await prepare_params(params, opts)

    cached = await cache.llm.check(cache_params)
    if cached.hit:
        return cached.response or ""

    response = await openai.responses.create(**params)

    blocks = []
    for item in response.output or []:
        if item.type == "message":
            for part in item.content or []:
                if part.type == "output_text":
                    blocks.append({"type": "text", "text": part.text})
        elif item.type == "reasoning":
            text = " ".join(s.text for s in (item.summary or []) if s.type == "reasoning_text")
            blocks.append({"type": "reasoning", "text": text})
        elif item.type == "function_call":
            import json
            try:
                args = json.loads(item.arguments or "{}")
            except json.JSONDecodeError:
                args = {"__raw": item.arguments}
            blocks.append({"type": "tool_call", "id": item.call_id, "name": item.name, "args": args})

    await cache.llm.store_multipart(cache_params, blocks, LlmStoreOptions(tokens={
        "input":  response.usage.input_tokens  if response.usage else 0,
        "output": response.usage.output_tokens if response.usage else 0,
    }))

    return " ".join(b["text"] for b in blocks if b.get("type") == "text")
```

`instructions` is prepended as a `system` message. The adapter handles `reasoning` items, `function_call`/`function_call_output` item types, and multi-modal input parts. `reasoning.effort` maps to `reasoning_effort` in the cache key.

---

## Anthropic Messages

```bash
pip install "betterdb-agent-cache[anthropic]"
```

```python
import valkey.asyncio as valkey_client
import anthropic as sdk
from betterdb_agent_cache import AgentCache, TierDefaults, compose_normalizer, hash_base64
from betterdb_agent_cache.adapters.anthropic import AnthropicPrepareOptions, prepare_params
from betterdb_agent_cache.types import AgentCacheOptions, LlmStoreOptions

client = valkey_client.Valkey(host="localhost", port=6379)
cache = AgentCache(AgentCacheOptions(
    client=client,
    tier_defaults={"llm": TierDefaults(ttl=3600)},
))
normalizer = compose_normalizer({"base64": hash_base64})
opts = AnthropicPrepareOptions(normalizer=normalizer)
anthropic = sdk.AsyncAnthropic()

async def chat(params: dict) -> str:
    cache_params = await prepare_params(params, opts)

    cached = await cache.llm.check(cache_params)
    if cached.hit:
        return cached.response or ""

    response = await anthropic.messages.create(**params)

    blocks = []
    for block in response.content:
        if block.type == "text":
            blocks.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            blocks.append({"type": "tool_call", "id": block.id, "name": block.name, "args": block.input})
        elif block.type == "thinking":
            blocks.append({"type": "reasoning", "text": block.thinking,
                           "opaqueSignature": getattr(block, "signature", None)})

    await cache.llm.store_multipart(cache_params, blocks, LlmStoreOptions(tokens={
        "input":  response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }))

    return " ".join(b["text"] for b in blocks if b.get("type") == "text")
```

`params["system"]` is prepended as a `system` message. `tool_result` blocks in user messages are split into separate `tool` messages. `thinking` and `redacted_thinking` blocks map to `reasoning` blocks. `stop_sequences` maps to `stop` in the cache key.

---

## LlamaIndex

```bash
pip install "betterdb-agent-cache[llamaindex]"
```

```python
import valkey.asyncio as valkey_client
from llama_index.llms.openai import OpenAI
from betterdb_agent_cache import AgentCache, TierDefaults, compose_normalizer, hash_base64
from betterdb_agent_cache.adapters.llamaindex import LlamaIndexPrepareOptions, prepare_params
from betterdb_agent_cache.types import AgentCacheOptions, LlmStoreOptions

client = valkey_client.Valkey(host="localhost", port=6379)
cache = AgentCache(AgentCacheOptions(
    client=client,
    tier_defaults={"llm": TierDefaults(ttl=3600)},
))
normalizer = compose_normalizer({"base64": hash_base64})
llm = OpenAI(model="gpt-4o-mini")

async def chat(messages: list) -> str:
    # model must be supplied explicitly — LlamaIndex messages don't carry it
    opts = LlamaIndexPrepareOptions(
        model="gpt-4o-mini",
        normalizer=normalizer,
        temperature=0,
    )
    cache_params = await prepare_params(messages, opts)

    cached = await cache.llm.check(cache_params)
    if cached.hit:
        return cached.response or ""

    response = await llm.achat(messages)
    text = str(response.message.content)
    blocks = [{"type": "text", "text": text}]

    usage = getattr(response.raw, "usage", None)
    await cache.llm.store_multipart(cache_params, blocks, LlmStoreOptions(tokens={
        "input":  getattr(usage, "prompt_tokens",     0) if usage else 0,
        "output": getattr(usage, "completion_tokens", 0) if usage else 0,
    }))
    return text
```

The model name is not available from LlamaIndex message objects — supply it via `LlamaIndexPrepareOptions.model`. The `memory` and `developer` roles are mapped to `system`. Tool calls are read from `message.options["toolCall"]` and tool results from `message.options["toolResult"]`.

---

## Adapter Import Paths

| Provider | Import path |
|---|---|
| OpenAI Chat Completions | `betterdb_agent_cache.adapters.openai` |
| OpenAI Responses API | `betterdb_agent_cache.adapters.openai_responses` |
| Anthropic Messages | `betterdb_agent_cache.adapters.anthropic` |
| LlamaIndex | `betterdb_agent_cache.adapters.llamaindex` |
| LangChain | `betterdb_agent_cache.adapters.langchain` |
| LangGraph | `betterdb_agent_cache.adapters.langgraph` |
