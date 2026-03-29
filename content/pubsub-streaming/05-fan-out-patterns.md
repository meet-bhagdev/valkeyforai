## Pattern 1: Pub/Sub Fan-Out (Live)  

```python
import valkey, json, time
client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

def broadcast_agent_event(agent_id, event_type, payload):
    """Broadcast to all subscribers watching this agent."""
    channel = f"agent:{agent_id}:events"
    message = {"type": event_type, "data": payload, "ts": time.time()}
    n = client.publish(channel, json.dumps(message))
    return n  # Number of receivers

# Dashboard, logger, metrics all receive this:
broadcast_agent_event("agent-1", "tool_call", {"tool": "search", "query": "valkey"})
```

## Pattern 2: Stream Fan-Out (Durable)

```python
# Multiple consumer groups on the SAME stream
# Each group gets ALL messages independently
client.xgroup_create("ai:events", "loggers", id="0", mkstream=True)
client.xgroup_create("ai:events", "metrics", id="0", mkstream=True)
client.xgroup_create("ai:events", "alerts", id="0", mkstream=True)

# Producer writes once
client.xadd("ai:events", {"event": "model_prediction", "latency_ms": "45"})
# All 3 groups get the message independently
```

## Pattern 3: Hybrid — Stream + Pub/Sub

```python
def publish_with_durability(event):
    """Write to Stream (durable) AND Pub/Sub (live)."""
    payload = json.dumps(event)
    client.xadd("ai:events", {"data": payload}, maxlen=50000)
    client.publish("ai:events:live", payload)
```

**When to use which:** Pub/Sub for real-time dashboards (missing messages OK). Streams with consumer groups for task queues (every message must be processed). Hybrid for both.

Pattern| Delivery| Durability| Best For  
---|---|---|---  
Pub/Sub| All subscribers| None| Live dashboards  
Stream + 1 group| One worker per msg| Persistent| Task queues  
Stream + N groups| All groups| Persistent| Event sourcing  
Hybrid| Both| Both| Full coverage