## Pattern 1: Feature Freshness Monitoring

Every feature Hash includes an `_updated_at` timestamp. Use it to detect stale features before they poison your model:

```python
import valkey
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

def check_freshness(feature_view: str, entity_id: str, threshold_seconds: float = 300):
    """Check if features are fresh enough for inference."""
    key = f"fs:v1:{feature_view}:{entity_id}"
    updated_at = client.hget(key, "_updated_at")

    if updated_at is None:
        return {"status": "missing", "age_seconds": None}

    age = time.time() - float(updated_at)

    return {
        "status": "fresh" if age < threshold_seconds else "stale",
        "age_seconds": round(age, 1),
        "threshold": threshold_seconds,
    }

# Check a single entity
result = check_freshness("user_risk_profile", "user_001", threshold_seconds=60)
print(result)
# {'status': 'fresh', 'age_seconds': 12.3, 'threshold': 60}
```

### Batch Freshness Check

```python
def batch_freshness_check(feature_view: str, entity_ids: list, threshold: float = 300):
    """Check freshness for multiple entities in one pipeline."""
    pipe = client.pipeline(transaction=False)
    for eid in entity_ids:
        pipe.hget(f"fs:v1:{feature_view}:{eid}", "_updated_at")

    results = pipe.execute()
    now = time.time()
    report = {"fresh": 0, "stale": 0, "missing": 0, "stale_entities": []}

    for eid, updated_at in zip(entity_ids, results):
        if updated_at is None:
            report["missing"] += 1
        elif now - float(updated_at) > threshold:
            report["stale"] += 1
            report["stale_entities"].append(eid)
        else:
            report["fresh"] += 1

    return report

# Check 100 entities
ids = [f"user_{i:03d}" for i in range(100)]
report = batch_freshness_check("user_risk_profile", ids, threshold=60)
print(report)
# {'fresh': 85, 'stale': 10, 'missing': 5, 'stale_entities': [...]}
```

### With the Library

```python
from src import ValkeyFeatureStore, Entity, FeatureView, Feature, FeatureType

store = ValkeyFeatureStore(host="localhost", port=6379)
# ... register feature views ...

# The monitor module provides freshness checking
fv = store.get_feature_view("user_risk_profile")
report = store.monitor.check_freshness(
    fv,
    entity_ids=["user_001", "user_002"],
    threshold_seconds=300,
)
print(report)
```

## Pattern 2: Health Checks

Add health checks to your deployment to detect issues early:

```python
def health_check() -> dict:
    """Full health check for the feature store."""
    health = {"status": "healthy", "checks": {}}

    # 1. Valkey connectivity
    try:
        start = time.time()
        client.ping()
        latency = (time.time() - start) * 1000
        health["checks"]["valkey_ping"] = {
            "status": "ok",
            "latency_ms": round(latency, 2),
        }
    except Exception as e:
        health["status"] = "unhealthy"
        health["checks"]["valkey_ping"] = {"status": "failed", "error": str(e)}

    # 2. Write/read test
    try:
        test_key = "fs:health_check"
        client.set(test_key, "ok", ex=10)
        val = client.get(test_key)
        health["checks"]["write_read"] = {"status": "ok" if val == "ok" else "failed"}
    except Exception as e:
        health["status"] = "unhealthy"
        health["checks"]["write_read"] = {"status": "failed", "error": str(e)}

    # 3. Memory usage
    try:
        info = client.info("memory")
        used_mb = info["used_memory"] / (1024 * 1024)
        max_mb = info.get("maxmemory", 0) / (1024 * 1024)
        health["checks"]["memory"] = {
            "used_mb": round(used_mb, 1),
            "max_mb": round(max_mb, 1) if max_mb > 0 else "unlimited",
            "status": "ok",
        }
    except Exception as e:
        health["checks"]["memory"] = {"status": "failed"}

    return health

print(health_check())
# {'status': 'healthy', 'checks': {'valkey_ping': {'status': 'ok', 'latency_ms': 0.12}, ...}}
```

### With the Library

```python
# Built-in health check
health = store.health()
print(health)

# Full info including registered views
info = store.info()
print(info)
# {'registered_views': ['user_profile', 'user_risk_profile'], 'health': {...}}
```

## Pattern 3: Feature Versioning

When your feature schema changes, use versioned key prefixes to migrate safely:

```python
# Current: fs:v1:user_profile:user_001
# New:     fs:v2:user_profile:user_001

# Step 1: Create v2 feature view with new schema
user_features_v2 = FeatureView(
    name="user_profile",
    entity=user,
    features=[
        Feature("age", FeatureType.INT),
        Feature("lifetime_value", FeatureType.FLOAT),
        Feature("segment", FeatureType.STRING),
        Feature("churn_risk", FeatureType.FLOAT),  # ← New feature
    ],
    version="v2",  # ← Version bump
    ttl=3600,
)

# Step 2: Dual-write during migration
def dual_write(entity_id, features, features_v2):
    """Write to both v1 and v2 during migration."""
    pipe = client.pipeline(transaction=False)

    # Write v1
    key_v1 = f"fs:v1:user_profile:{entity_id}"
    pipe.hset(key_v1, mapping={k: str(v) for k, v in features.items()})
    pipe.expire(key_v1, 3600)

    # Write v2 (includes new fields)
    key_v2 = f"fs:v2:user_profile:{entity_id}"
    pipe.hset(key_v2, mapping={k: str(v) for k, v in features_v2.items()})
    pipe.expire(key_v2, 3600)

    pipe.execute()

# Step 3: Migrate readers to v2
# Step 4: Stop writing to v1
# Step 5: Let v1 keys expire naturally (TTL)
```

**Zero-downtime migration:** Because Valkey keys include the version prefix, v1 and v2 coexist safely. Dual-write during migration, switch readers, then let v1 expire. No data loss, no downtime.

## Pattern 4: Connection Pooling

In production, always use connection pooling to avoid creating a new TCP connection per request:

```python
import valkey

# Create a connection pool (once at app startup)
pool = valkey.ConnectionPool(
    host="localhost",
    port=6379,
    max_connections=50,    # Max concurrent connections
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=2,
    retry_on_timeout=True,
)

# Create client from pool (cheap — reuses connections)
client = valkey.Valkey(connection_pool=pool)

# Use with the feature store library
store = ValkeyFeatureStore(client=client)

# Check pool stats
print(f"Pool connections: {len(pool._available_connections)}")
```

## Pattern 5: Error Handling & Fallbacks

Handle Valkey failures gracefully — don't let a cache miss crash your prediction:

```python
def safe_read_features(store, view_name: str, entity_id: str, defaults: dict = None):
    """Read features with error handling and fallback defaults."""
    try:
        features = store.read(view_name, entity_id)
        if features:
            return features
    except redis.ConnectionError:
        # Valkey is down — use defaults
        print(f"⚠️ Valkey connection error, using defaults")
    except redis.TimeoutError:
        # Valkey is slow — use defaults
        print(f"⚠️ Valkey timeout, using defaults")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")

    # Return defaults so the model can still make a prediction
    return defaults or {}

# Usage
features = safe_read_features(store, "user_risk_profile", "user_001",
    defaults={"txn_count_1h": 0, "avg_txn_amount": 50.0, "fraud_score": 0.5})
```

## Pattern 6: Observability Metrics

Track key metrics for your feature store in production:

```python
def get_store_metrics() -> dict:
    """Collect feature store metrics for monitoring dashboards."""
    info = client.info()

    return {
        # Throughput
        "ops_per_second": info.get("instantaneous_ops_per_sec", 0),

        # Memory
        "memory_used_mb": round(info["used_memory"] / 1048576, 1),
        "memory_peak_mb": round(info["used_memory_peak"] / 1048576, 1),

        # Connections
        "connected_clients": info.get("connected_clients", 0),

        # Keys
        "total_keys": info.get("db0", {}).get("keys", 0),

        # Hit rate (if using Valkey as cache too)
        "keyspace_hits": info.get("keyspace_hits", 0),
        "keyspace_misses": info.get("keyspace_misses", 0),
    }

metrics = get_store_metrics()
print(metrics)
# {'ops_per_second': 1250, 'memory_used_mb': 45.2, ...}
```

## Production Checklist

Area| Pattern| Recommendation  
---|---|---  
Connections| Connection pooling| Use `ConnectionPool` with `max_connections=50`  
Timeouts| Socket timeouts| Set `socket_timeout=2`, `socket_connect_timeout=5`  
Retries| Retry on timeout| Enable `retry_on_timeout=True`  
Freshness| Staleness detection| Check `_updated_at` before inference, alert on stale  
TTL| Feature expiry| Set TTL on all feature views (e.g., 1h–24h)  
Versioning| Key prefix versions| Use `fs:v1:`, `fs:v2:` for schema changes  
Fallbacks| Default values| Always have sensible defaults for model features  
Monitoring| Health checks| Ping + write/read test on `/health` endpoint  
Memory| Maxmemory policy| Set `maxmemory-policy allkeys-lru` in production  
Persistence| RDB/AOF| Enable RDB snapshots for feature store durability  
  
**Congratulations!** You've completed all 6 cookbooks. You now know how to build, serve, stream, integrate, and operate a production feature store with Valkey. Check out the [interactive demo](</demo/feature-store.html>) to experiment with these patterns in your browser.