## Share a Session Across Multiple Agents

A single session can hold state for multiple agents - each gets its own agent key and message keys under the same session ID. This is the foundation for orchestrator/subagent patterns where agents need to share context:

```python
import os
from dotenv import load_dotenv

load_dotenv()

from strands import Agent
from strands_valkey_session_manager import ValkeySessionManager
import valkey

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Two agents sharing the same session_id
researcher = Agent(
    system_prompt="You are a research agent.",
    session_manager=ValkeySessionManager(
        session_id="workflow-001", client=client
    ),
)
writer = Agent(
    system_prompt="You are a writing agent.",
    session_manager=ValkeySessionManager(
        session_id="workflow-001", client=client
    ),
)

researcher("Research the key benefits of Valkey for AI workloads.")
writer("Write a short blog intro about Valkey for AI.")

# Each agent has its own message keys under the same session
# session:workflow-001:agent:researcher:message:<id>
# session:workflow-001:agent:writer:message:<id>
```

## Clean Up on Logout

Call `delete_session()` to remove all keys for a session - the session record, agent state, and every message - in one call:

```python
import valkey
from strands_valkey_session_manager import ValkeySessionManager

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)
sm = ValkeySessionManager(session_id="user-42", client=client)

# Removes session, agent state, and all messages for this session
sm.delete_session("user-42")
print("Session deleted")
```

## Query Valkey Directly

You can inspect the raw keys at any time to see exactly what's stored and how long until each key expires:

```python
# List all keys for a session with their TTLs
keys = client.keys("session:user-42*")
for k in sorted(keys):
    ttl = client.ttl(k)
    print(f"{k}  (TTL: {ttl}s)")

# session:user-42                                              (TTL: 3598s)
# session:user-42:agent:default                                (TTL: 3597s)
# session:user-42:agent:default:message:<uuid>                 (TTL: 3596s)
# session:user-42:agent:default:message:<uuid>                 (TTL: 3596s)
```
