"""Integration tests for Rate Limiting - Hierarchical Rate Limiting.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_04_hierarchical(client):
    """Run all code blocks from: Hierarchical Rate Limiting."""

    # --- Block 1 ---
    from dataclasses import dataclass

    @dataclass
    class Tier:
        name: str           # "org", "team", "user", "agent", "model"
        identifier: str     # "acme-corp", "engineering", "alice"
        max_requests: int
        max_tokens: int
        window_seconds: int

    tiers = [
        Tier("org", "acme-corp", 10000, 1_000_000, 3600),
        Tier("team", "engineering", 5000, 500_000, 3600),
        Tier("user", "alice", 1000, 100_000, 3600),
        Tier("agent", "agent-research-1", 200, 25_000, 3600),
    ]

    # --- Block 2 ---
    def hierarchical_check(tiers: list, tokens: int) -> dict:
        now = time.time()

        # Phase 1: Read all counters in one pipeline
        pipe = client.pipeline(transaction=False)
        for tier in tiers:
            window_num = int(now // tier.window_seconds)
            pipe.get(f"hier:{tier.name}:{tier.identifier}:req:{window_num}")
            pipe.get(f"hier:{tier.name}:{tier.identifier}:tok:{window_num}")
        results = pipe.execute()

        # Phase 2: Check each tier
        blocked_by = None
        for i, tier in enumerate(tiers):
            current_req = int(results[i * 2] or 0)
            current_tok = int(results[i * 2 + 1] or 0)
            if current_req + 1 > tier.max_requests or current_tok + tokens > tier.max_tokens:
                blocked_by = tier.name
                break

        # Phase 3: If allowed, increment all tiers atomically
        if not blocked_by:
            pipe = client.pipeline(transaction=True)
            for tier in tiers:
                window_num = int(now // tier.window_seconds)
                req_key = f"hier:{tier.name}:{tier.identifier}:req:{window_num}"
                tok_key = f"hier:{tier.name}:{tier.identifier}:tok:{window_num}"
                pipe.incr(req_key); pipe.expire(req_key, tier.window_seconds)
                pipe.incrby(tok_key, tokens); pipe.expire(tok_key, tier.window_seconds)
            pipe.execute()

        return {"allowed": blocked_by is None, "blocked_by": blocked_by}

