## Prerequisites

  * Docker installed (or a running Valkey instance)
  * Python 3.9+

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey:latest
```

Verify it's running:

```bash
docker exec valkey valkey-cli ping
# PONG
```

## Step 2: Install Dependencies

```bash
pip install valkey
```

That's it — no special libraries needed. The `redis` Python package works with Valkey out of the box.

## Step 3: Your First Rate Limiter

```python
import valkey
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

def check_rate_limit(user_id: str, max_requests: int = 10, window: int = 60) -> dict:
    """Fixed-window rate limiter."""
    window_num = int(time.time() // window)
    key = f"rl:{user_id}:{window_num}"

    pipe = client.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, window)
    results = pipe.execute()

    current = results[0]
    allowed = current <= max_requests

    return {
        "allowed": allowed,
        "current": current,
        "limit": max_requests,
        "remaining": max(0, max_requests - current),
    }
```

## Step 4: Test It

```python
# Send 12 requests — last 2 should be denied
for i in range(12):
    result = check_rate_limit("user-123", max_requests=10)
    status = "✅" if result["allowed"] else "❌"
    print(f"{status} Request {i+1}: {result['current']}/{result['limit']}")
```

**Output:**

```python
✅ Request 1: 1/10
✅ Request 2: 2/10
...
✅ Request 10: 10/10
❌ Request 11: 11/10
❌ Request 12: 12/10
```

## How It Works

**Key Insight:** We use `INCR` \+ `EXPIRE` in a pipeline. The key includes the window number (current timestamp ÷ window size), so it auto-rotates every window. Valkey handles all the atomic counting — no race conditions.

Operation| Valkey Command| Time  
---|---|---  
Increment counter| `INCR`| ~0.1ms  
Set expiry| `EXPIRE`| ~0.1ms  
Pipeline (both)| 1 round-trip| ~0.2ms total  
[ Next → 02 — Token-Aware Limiting ](<02-token-aware.html>)