"""Integration tests for Rate Limiting - Token-Aware Rate Limiting.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_02_token_aware(client):
    """Run all code blocks from: Token-Aware Rate Limiting."""

    # --- Block 1 ---
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

    # --- Block 2 ---
    import time

    client = client

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

    # --- Block 3 ---
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

    # --- Block 4 ---
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

