"""Integration tests for Rate Limiting - Cost-Based Rate Limiting.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_05_cost_based(client):
    """Run all code blocks from: Cost-Based Rate Limiting."""

    # --- Block 1 ---
    MODEL_COSTS = {
        "gpt-4":          {"input": 0.030, "output": 0.060},
        "gpt-4o":         {"input": 0.005, "output": 0.015},
        "gpt-3.5-turbo":  {"input": 0.001, "output": 0.002},
        "claude-3-opus":  {"input": 0.015, "output": 0.075},
        "claude-3-sonnet":{"input": 0.003, "output": 0.015},
    }

    def calculate_cost(input_tokens, output_tokens, model):
        pricing = MODEL_COSTS.get(model, {"input": 0.01, "output": 0.02})
        return round(
            (input_tokens / 1000) * pricing["input"] +
            (output_tokens / 1000) * pricing["output"], 6
        )

    # --- Block 2 ---
    def check_budget(identifier, estimated_cost, budget=10.00, window=3600):
        window_num = int(time.time() // window)
        key = f"budget:{identifier}:{window_num}"

        current = float(client.get(key) or 0)

        if current + estimated_cost <= budget:
            client.incrbyfloat(key, estimated_cost)
            client.expire(key, window)
            return {"allowed": True, "remaining": f"${budget - current - estimated_cost:.4f}"}
        else:
            return {"allowed": False, "remaining": f"${max(0, budget - current):.4f}"}

    # --- Block 3 ---
    def smart_model_select(identifier, preferred_model="gpt-4"):
        window_num = int(time.time() // 3600)
        current_spend = float(client.get(f"budget:{identifier}:{window_num}") or 0)
        budget = 10.00
        remaining_pct = (budget - current_spend) / budget

        if remaining_pct > 0.5:
            return preferred_model              # Plenty of budget
        elif remaining_pct > 0.2:
            return {"gpt-4": "gpt-4o"}.get(preferred_model, preferred_model)
        elif remaining_pct > 0.05:
            return "gpt-3.5-turbo"             # Emergency mode
        else:
            raise Exception("Budget exhausted")

    # --- Block 4 ---
    def track_spend(identifier, cost, model):
        now = datetime.utcnow()
        pipe = client.pipeline()
        # Hourly, daily, monthly buckets
        pipe.incrbyfloat(f"spend:{identifier}:hour:{now:%Y%m%d%H}", cost)
        pipe.expire(f"spend:{identifier}:hour:{now:%Y%m%d%H}", 7200)
        pipe.incrbyfloat(f"spend:{identifier}:day:{now:%Y%m%d}", cost)
        pipe.expire(f"spend:{identifier}:day:{now:%Y%m%d}", 172800)
        pipe.incrbyfloat(f"spend:{identifier}:month:{now:%Y%m}", cost)
        pipe.expire(f"spend:{identifier}:month:{now:%Y%m}", 2764800)
        pipe.execute()

