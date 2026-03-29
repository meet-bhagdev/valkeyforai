[← All RAG Cookbooks](</cookbooks/rag-pipelines/>)

# Scaling for Production

Handle millions of vectors with clustering, replication, and memory optimization.

## Memory Estimation

Plan your infrastructure based on vector count and dimensions:

Vectors| Dimensions| ~Memory (HNSW)  
---|---|---  
100K| 1536| ~1 GB  
1M| 1536| ~10 GB  
10M| 1536| ~100 GB  
100M| 1536| ~1 TB (cluster)  
  
Formula: vectors × dimensions × 4 bytes × 1.5 (HNSW overhead)

## Cluster Mode

Distribute data across multiple nodes for horizontal scaling:

```yaml
# Docker Compose for 3-node cluster
version: '3.8'
services:
  valkey-1:
    image: valkey/valkey-bundle:latest
    command: valkey-server --cluster-enabled yes --cluster-node-timeout 5000
    ports:
      - "7001:6379"

  valkey-2:
    image: valkey/valkey-bundle:latest
    command: valkey-server --cluster-enabled yes --cluster-node-timeout 5000
    ports:
      - "7002:6379"

  valkey-3:
    image: valkey/valkey-bundle:latest
    command: valkey-server --cluster-enabled yes --cluster-node-timeout 5000
    ports:
      - "7003:6379"
```

```bash
# Create cluster
valkey-cli --cluster create \
  127.0.0.1:7001 127.0.0.1:7002 127.0.0.1:7003 \
  --cluster-replicas 0
```

## Replication for HA

```bash
# valkey.conf for replica
replicaof primary.host 6379
replica-read-only yes
```

```python
# Connect to replicas for read scaling
primary = valkey.Valkey(host='primary', port=6379)
replica = valkey.Valkey(host='replica', port=6379)

# Write to primary, read from replicas
primary.hset(key, mapping=data)
results = replica.ft('idx').search(query)
```

## Memory Optimization

```bash
# valkey.conf optimizations
maxmemory 8gb
maxmemory-policy volatile-lru

# Use FLOAT16 for 50% memory savings (slight accuracy loss)
FT.CREATE idx ON HASH PREFIX 1 "doc:"
  SCHEMA
    embedding VECTOR HNSW 6
      TYPE FLOAT16   # Instead of FLOAT32
      DIM 1536
      DISTANCE_METRIC COSINE

# Enable compression for hash values
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
```

## Connection Pooling

```python
# Use connection pools in production
pool = valkey.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50,
    decode_responses=False
)
client = valkey.Valkey(connection_pool=pool)

# Or use async with connection pool
pool = valkey.asyncio.ConnectionPool.from_url(
    "redis://localhost:6379",
    max_connections=50
)
```

## AWS ElastiCache / MemoryDB

```python
# Connect to ElastiCache cluster
client = valkey.Valkey(
    host='my-cluster.cache.amazonaws.com',
    port=6379,
    ssl=True,
    ssl_cert_reqs='required'
)

# For cluster mode
from redis.cluster import RedisCluster

cluster = RedisCluster(
    host='my-cluster.cache.amazonaws.com',
    port=6379,
    ssl=True
)
```

[← Cache Invalidation](<04-cache-invalidation.html>) [Next: Monitoring →](<06-monitoring.html>)
