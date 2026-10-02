## Pub/Sub vs Streams  
  
Feature| Pub/Sub| Streams  
---|---|---  
Durability| Ephemeral| Persistent until trimmed  
Replay| No| Yes - XRANGE  
Consumer groups| No| Yes  
Ordering| No guarantees| Strict by ID  
Backpressure| None| MAXLEN trimming  
  
## Step 1: Add Messages

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey, json, time
client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# XADD - append to stream
entry_id = client.xadd("ai:tasks", {
    "type": "embedding",
    "text": "Hello world",
    "model": "text-embedding-3-small",
})
print(f"Added: {entry_id}")

# With MAXLEN cap
client.xadd("ai:tasks", {"type": "completion"}, maxlen=10000)
```

## Step 2: Read Messages

```python
# XREAD - blocking read for new messages
entries = client.xread({"ai:tasks": "0-0"}, count=10, block=5000)
for stream, messages in entries:
    for msg_id, data in messages:
        print(f"[{msg_id}] {data}")

# XRANGE - replay from beginning
messages = client.xrange("ai:tasks", min="-", max="+", count=5)

# XREVRANGE - newest first
latest = client.xrevrange("ai:tasks", max="+", min="-", count=1)
```

## Step 3: Stream Management

```python
length = client.xlen("ai:tasks")
info = client.xinfo_stream("ai:tasks")
client.xtrim("ai:tasks", maxlen=1000)
```

## Step 4: Consumer Loop

```python
def consume(stream_key):
    last_id = "$"  # Only new messages
    while True:
        entries = client.xread({stream_key: last_id}, count=10, block=2000)
        if not entries: continue
        for stream, messages in entries:
            for msg_id, data in messages:
                print(f"Processing: {data}")
                last_id = msg_id
```

**Key:** Use `"$"` for new messages only, `"0-0"` to replay from start.

Command| Purpose| Latency  
---|---|---  
`XADD`| Append message| ~0.1ms  
`XREAD BLOCK`| Wait for new| ~0.1ms + block  
`XRANGE`| Read range / replay| ~0.1ms  
`XLEN`| Stream length| ~0.1ms  
`XTRIM`| Cap stream size| ~0.1ms