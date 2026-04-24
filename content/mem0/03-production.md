## Step 1: ElastiCache for Valkey 8.2+

ElastiCache for Valkey 8.2 includes built-in vector search at no additional cost. Create a cluster via the AWS Console or CLI, then use the cluster endpoint as your Valkey URL.

```python
import os
from dotenv import load_dotenv

load_dotenv()

from mem0 import Memory

config = {
    "vector_store": {
        "provider": "valkey",
        "config": {
            # Use your ElastiCache cluster endpoint
            "valkey_url": "valkey://your-cluster.xxxxx.use1.cache.amazonaws.com:6379",
            "collection_name": "prod_memories",
            "embedding_model_dims": 1536,
            "index_type": "hnsw",
            # HNSW tuning parameters
            "hnsw_m": 16,              # connections per node
            "hnsw_ef_construction": 200, # build-time search width
            "hnsw_ef_runtime": 10,      # query-time search width
        }
    }
}
memory = Memory.from_config(config)
```

## Step 2: HNSW Parameter Tuning

Parameter| Default| Effect| Recommendation  
---|---|---|---  
`hnsw_m`| 16| More connections = higher recall, more memory| 16 for most cases, 32 for >1M memories  
`hnsw_ef_construction`| 200| Higher = better index quality, slower build| 200 default, increase to 400 for critical apps  
`hnsw_ef_runtime`| 10| Higher = better recall, higher latency| 10 for speed, 50+ for maximum recall  
`index_type`| hnsw| HNSW=fast approximate, FLAT=exact| HNSW for >1000 memories, FLAT for small sets  
  
## Step 3: TLS for ElastiCache

```python
# ElastiCache with TLS enabled
config = {
    "vector_store": {
        "provider": "valkey",
        "config": {
            "valkey_url": "valkeys://your-cluster.xxxxx.use1.cache.amazonaws.com:6379",
            # Note: valkeys:// (with 's') enables TLS
            "collection_name": "prod_memories",
            "embedding_model_dims": 1536,
        }
    }
}
```

## Step 4: Monitoring

```python
import valkey

# Connect directly to check index health
client = valkey.from_url("valkey://your-cluster:6379")

# Check index info
info = client.execute_command("FT.INFO", "prod_memories")
print(info)

# Check memory usage
mem_info = client.info("memory")
print(f"Used: {mem_info['used_memory_human']}")

# Count memories per user
results = client.execute_command(
    "FT.SEARCH", "prod_memories",
    "@user_id:{alice}",
    "LIMIT", "0", "0",  # count only
)
print(f"Alice has {results[0]} memories")
```

## Production Checklist

Area| Recommendation  
---|---  
ElastiCache| Use Valkey 8.2+ for built-in vector search  
TLS| Use `valkeys://` URL scheme for encrypted connections  
Multi-AZ| Enable for high availability  
HNSW M| 16 default, 32 for large memory stores  
Embedding model| text-embedding-3-small (1536 dims, fast, cheap)  
Memory limits| Use maxmemory-policy to handle full memory  
Monitoring| Track FT.INFO for index size + memory usage  
  
**Source:** Mem0's Valkey connector: [valkey.py](<https://github.com/mem0ai/mem0/blob/main/mem0/vector_stores/valkey.py>) and config: [ValkeyConfig](<https://github.com/mem0ai/mem0/blob/main/mem0/configs/vector_stores/valkey.py>)