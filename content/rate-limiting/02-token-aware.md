## The Problem

```python
User makes 3 requests:
  Request 1: "Hi" → 5 tokens
  Request 2: "Summarize this 200-page PDF" → 45,000 tokens
  Request 3: "Thanks" → 3 tokens

A request-based limiter treats all 3 the same. That's wrong.
```

## Step 1: Count Tokens Before Calling the LLM

```python
import os
from dotenv import load_dotenv

load_dotenv()

import tiktoken

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens using tiktoken (OpenAI's tokenizer)."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

# Examples
print(count_tokens("Hello world"))           # ~2
print(count_tokens("Explain quantum physics in detail"))  # ~6
```

## Step 2: Token-Aware Fixed Window

```python
import valkey
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

def check_token_limit(
    identifier: str,
    input_tokens: int,
    max_tokens: int = 100_000,
    window: int = 60,
) -> dict:
    """Rate limit by token consumption per window."""
    window_num = int(time.time() // window)
    key = f"tl:{identifier}:tok:{window_num}"

    # Atomic: get current count, then increment
    pipe = client.pipeline(transaction=True)
    pipe.get(key)
    pipe.incrby(key, input_tokens)
    pipe.expire(key, window)
    results = pipe.execute()

    current_before = int(results[0] or 0)
    allowed = current_before + input_tokens <= max_tokens

    if not allowed:
        client.decrby(key, input_tokens)  # Rollback

    return {
        "allowed": allowed,
        "tokens_used": current_before,
        "tokens_remaining": max(0, max_tokens - current_before),
        "max_tokens": max_tokens,
    }
```

## Step 3: Dual Limiting (Requests + Tokens)

Most production systems limit **both** - you don't want a user making 10,000 tiny requests either:

```python
def dual_limit_check(
    identifier: str,
    tokens: int,
    max_requests: int = 60,
    max_tokens: int = 100_000,
    window: int = 60,
) -> dict:
    """Limit by both request count AND token count."""
    window_num = int(time.time() // window)
    req_key = f"dl:{identifier}:req:{window_num}"
    tok_key = f"dl:{identifier}:tok:{window_num}"

    pipe = client.pipeline(transaction=True)
    pipe.incr(req_key)
    pipe.expire(req_key, window)
    pipe.incrby(tok_key, tokens)
    pipe.expire(tok_key, window)
    results = pipe.execute()

    req_count = results[0]
    tok_count = results[2]

    req_ok = req_count <= max_requests
    tok_ok = tok_count <= max_tokens
    allowed = req_ok and tok_ok

    blocked_by = None
    if not req_ok: blocked_by = "requests"
    elif not tok_ok: blocked_by = "tokens"

    return {
        "allowed": allowed,
        "blocked_by": blocked_by,
        "requests": f"{req_count}/{max_requests}",
        "tokens": f"{tok_count}/{max_tokens}",
    }
```

## Step 4: Estimate Output Tokens

Input tokens are known. Output tokens aren't - but you can **estimate** them and adjust after:

```python
OUTPUT_MULTIPLIERS = {
    "gpt-4": 1.5,
    "gpt-4o": 1.2,
    "gpt-3.5-turbo": 1.0,
    "claude-3-sonnet": 1.3,
}

def estimate_total_tokens(input_tokens: int, model: str) -> int:
    multiplier = OUTPUT_MULTIPLIERS.get(model, 1.2)
    estimated_output = int(input_tokens * multiplier)
    return input_tokens + estimated_output
```

**Pro Tip:** Pre-estimate before the LLM call, then adjust with actual usage after. This gives you accurate budget tracking while still gating before the expensive call happens.

## Key Takeaways

Pattern| When to Use  
---|---  
Token-only limiting| When request count doesn't matter (batch jobs)  
Dual (request + token)| Production API gateways  
Pre-estimate + post-adjust| High-accuracy budget tracking