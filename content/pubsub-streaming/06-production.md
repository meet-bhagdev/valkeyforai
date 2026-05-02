## Pattern 1: Backpressure with MAXLEN  

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey, time
client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Approximate trim (faster, recommended)
client.xadd("ai:tasks", {"data": "..."}, maxlen=10000)

# Time-based trim (remove entries older than 1 hour)
cutoff_ms = int((time.time() - 3600) * 1000)
client.xtrim("ai:tasks", minid=cutoff_ms)
```

## Pattern 2: Monitoring with XINFO

```python
def stream_health(stream_key):
    info = client.xinfo_stream(stream_key)
    groups = client.xinfo_groups(stream_key)
    return {
        "length": info["length"],
        "groups": len(groups),
        "consumers": sum(g["consumers"] for g in groups),
        "pending": sum(g["pending"] for g in groups),
    }
print(stream_health("ai:tasks"))
```

## Pattern 3: Resilient Pub/Sub Subscriber

```python
def resilient_subscriber(channel):
    while True:
        try:
            c = valkey.Valkey(host="localhost", decode_responses=True)
            ps = c.pubsub()
            ps.subscribe(channel)
            print(f"Connected to {channel}")
            for msg in ps.listen():
                if msg["type"] == "message":
                    print(msg["data"])
        except valkey.ConnectionError:
            print("Disconnected, reconnecting in 2s...")
            time.sleep(2)
```

## Pattern 4: Dead Letter Queue

```python
def process_with_dlq(stream, group, consumer, max_retries=3):
    entries = client.xreadgroup(group, consumer, {stream: ">"}, count=10, block=2000)
    if not entries: return
    for s, messages in entries:
        for msg_id, data in messages:
            try:
                process(data)
                client.xack(stream, group, msg_id)
            except Exception:
                # After max retries, move to DLQ
                pending = client.xpending_range(stream, group, msg_id, msg_id, 1)
                if pending and pending[0]["times_delivered"] >= max_retries:
                    client.xadd(f"{stream}:dlq", data)
                    client.xack(stream, group, msg_id)
```

## Production Checklist

Area| Recommendation  
---|---  
Backpressure| Always use `MAXLEN` on XADD  
Monitoring| Track stream length, pending count, consumer lag  
Reconnection| Wrap Pub/Sub listeners in retry loops  
Acknowledgments| Always XACK after processing  
Dead letters| Move failed messages to DLQ after N retries  
Scaling| Add consumers to groups for horizontal scale  
Memory| Use XTRIM or MAXLEN to bound stream size  
  
**Congrats!** You completed all 6 Pub/Sub & Streaming cookbooks. Check out the [interactive demo](</demo/pubsub-streaming.html>) to experiment.