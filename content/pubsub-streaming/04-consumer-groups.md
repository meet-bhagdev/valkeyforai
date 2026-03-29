## Why Consumer Groups?  
  
With plain XREAD, every consumer gets every message. With consumer groups, messages are distributed — enabling parallel processing of AI tasks like embeddings, completions, and tool calls.

## Step 1: Create a Group

```python
import valkey
client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

try:
    client.xgroup_create("ai:tasks", "workers", id="0", mkstream=True)
except valkey.ResponseError:
    pass  # Group already exists
```

## Step 2: Consume from Group

```python
def worker(worker_name: str):
    while True:
        entries = client.xreadgroup(
            "workers", worker_name,
            {"ai:tasks": ">"},
            count=5, block=2000,
        )
        if not entries: continue
        for stream, messages in entries:
            for msg_id, data in messages:
                print(f"[{worker_name}] Processing: {data}")
                # Process the task...
                client.xack("ai:tasks", "workers", msg_id)
```

## Step 3: Handle Pending Messages

```bash
# Check unacknowledged messages
pending = client.xpending("ai:tasks", "workers")
print(f"Pending: {pending}")

# Claim stuck messages (idle > 30s)
claimed = client.xclaim(
    "ai:tasks", "workers", "worker-2",
    min_idle_time=30000,
    message_ids=["1710000000000-0"],
)
```

**At-least-once delivery:** Messages stay pending until XACK. If a worker crashes, use XPENDING + XCLAIM to reassign to a healthy worker.

Command| Purpose  
---|---  
`XGROUP CREATE`| Create consumer group  
`XREADGROUP`| Read as group member  
`XACK`| Acknowledge processing  
`XPENDING`| List unacknowledged  
`XCLAIM`| Reassign stuck messages