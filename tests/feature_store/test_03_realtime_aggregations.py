"""Integration tests for Feature Store - Real-time Aggregations.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_realtime_aggregations(client):
    """Run all code blocks from: Real-time Aggregations."""

    # --- Block 1 ---
    import time
    import uuid

    client = client

    def record_event(user_id: str, window_seconds: int = 3600):
        """Record an event and return the count in the sliding window."""
        key = f"fs:agg:txn_count:{user_id}"
        now = time.time()
        cutoff = now - window_seconds

        pipe = client.pipeline(transaction=True)

        # 1. Add this event with timestamp as score
        pipe.zadd(key, {str(uuid.uuid4()): now})

        # 2. Remove events outside the window
        pipe.zremrangebyscore(key, "-inf", cutoff)

        # 3. Count remaining events in window
        pipe.zcard(key)

        # 4. Set TTL so the key self-cleans if user goes inactive
        pipe.expire(key, window_seconds * 2)

        results = pipe.execute()
        count = results[2]  # zcard result

        return count

    # Usage
    for i in range(5):
        count = record_event("user_001", window_seconds=60)
        print(f"Transactions in last 60s: {count}")
    # Transactions in last 60s: 1
    # Transactions in last 60s: 2
    # Transactions in last 60s: 3
    # ...

    # --- Block 2 ---
    def update_running_average(user_id: str, amount: float):
        """Update running average and return new value."""
        sum_key = f"fs:agg:txn_sum:{user_id}"
        count_key = f"fs:agg:txn_count_total:{user_id}"

        pipe = client.pipeline(transaction=True)
        pipe.incrbyfloat(sum_key, amount)
        pipe.incr(count_key)
        pipe.expire(sum_key, 86400)   # 24h TTL
        pipe.expire(count_key, 86400)
        results = pipe.execute()

        total_sum = float(results[0])
        total_count = int(results[1])
        avg = total_sum / total_count if total_count > 0 else 0

        return {"sum": total_sum, "count": total_count, "average": round(avg, 2)}

    # Usage
    amounts = [25.00, 150.00, 12.50, 89.99]
    for amt in amounts:
        result = update_running_average("user_001", amt)
        print(f"${amt:>7.2f} → avg=${result['average']}")
    # $ 25.00 → avg=$25.0
    # $150.00 → avg=$87.5
    # $ 12.50 → avg=$62.5
    # $ 89.99 → avg=$69.37

    # --- Block 3 ---
    def record_unique_merchant(user_id: str, merchant_id: str):
        """Track unique merchants and return approximate count."""
        key = f"fs:agg:unique_merchants:{user_id}"

        pipe = client.pipeline(transaction=True)
        pipe.pfadd(key, merchant_id)     # Add to HyperLogLog
        pipe.pfcount(key)                # Get approximate count
        pipe.expire(key, 86400)          # 24h TTL
        results = pipe.execute()

        return results[1]  # pfcount result

    # Usage
    merchants = ["amazon", "walmart", "amazon", "target", "starbucks", "amazon"]
    for m in merchants:
        count = record_unique_merchant("user_001", m)
        print(f"After {m}: {count} unique merchants")
    # After amazon: 1 unique merchants
    # After walmart: 2 unique merchants
    # After amazon: 2 unique merchants   ← duplicate, no change
    # After target: 3 unique merchants
    # After starbucks: 4 unique merchants
    # After amazon: 4 unique merchants   ← duplicate, no change

    # --- Block 4 ---
    def materialize_user_features(user_id: str):
        """Compute aggregations and write to the feature store Hash."""
        pipe = client.pipeline(transaction=False)

        # Read aggregation state
        now = time.time()
        pipe.zcount(f"fs:agg:txn_count:{user_id}", now - 3600, now)
        pipe.get(f"fs:agg:txn_sum:{user_id}")
        pipe.get(f"fs:agg:txn_count_total:{user_id}")
        pipe.pfcount(f"fs:agg:unique_merchants:{user_id}")
        results = pipe.execute()

        txn_count_1h = results[0] or 0
        txn_sum = float(results[1] or 0)
        txn_total = int(results[2] or 0)
        unique_merchants = results[3] or 0

        avg_amount = txn_sum / txn_total if txn_total > 0 else 0

        # Write to feature store Hash
        feature_key = f"fs:v1:user_risk_profile:{user_id}"
        features = {
            "txn_count_1h": str(txn_count_1h),
            "avg_txn_amount": str(round(avg_amount, 2)),
            "unique_merchants_24h": str(unique_merchants),
            "_updated_at": str(now),
        }
        client.hset(feature_key, mapping=features)
        client.expire(feature_key, 86400)

        return features

