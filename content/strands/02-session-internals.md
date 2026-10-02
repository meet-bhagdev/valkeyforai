## What Gets Stored Per Session

### Session Record

One record per conversation. Tracks when the session was created and last updated.

```json
{
  "session_id": "user-42",
  "created_at": "2025-06-01T10:00:00+00:00",
  "updated_at": "2025-06-01T10:05:32+00:00",
  "metadata": {}
}
```

### Agent State

One record per agent within a session. Tracks message count and interrupt state so the agent can resume exactly where it left off.

```json
{
  "agent_id": "default",
  "session_id": "user-42",
  "conversation_manager_state": {
    "message_count": 4
  },
  "interrupt_state": null
}
```

### Conversation Messages

One record per turn. Stores the role (user or assistant), content text, any tool calls or results, and a timestamp.

```json
{
  "message_id": "3f8a1c2d-...",
  "role": "user",
  "content": [
    {"text": "My name is Alex and I'm building a RAG pipeline."}
  ],
  "created_at": "2025-06-01T10:00:01+00:00"
}
```

Assistant message with tool use:

```json
{
  "message_id": "7b2e9f4a-...",
  "role": "assistant",
  "content": [
    {"text": "Nice to meet you, Alex! ..."},
    {"toolUse": {"toolUseId": "...", "name": "search", "input": {"query": "RAG pipeline"}}}
  ],
  "created_at": "2025-06-01T10:00:03+00:00"
}
```

## Pick Up Where You Left Off

Create a new `Agent` with the same `session_id` - Strands reloads the full conversation history from Valkey automatically:

```python
import os
from dotenv import load_dotenv

load_dotenv()

import valkey
from strands import Agent
from strands_valkey_session_manager import ValkeySessionManager

# In a new Python process - history is restored from Valkey
client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)
session_manager = ValkeySessionManager(
    session_id="user-42",  # same session ID
    client=client,
)
agent = Agent(session_manager=session_manager)

response = agent("What was I just telling you about?")
print(response)
# Agent correctly recalls: "You mentioned you're building a RAG pipeline."
```

## See What Got Saved

```python
# List all messages for this session
messages = session_manager.list_messages()
for msg in messages:
    print(f"[{msg['role']}] {str(msg['content'])[:80]}")

# Or inspect raw keys directly
keys = client.keys("session:user-42*")
for k in sorted(keys):
    print(k)
```

## Read and Update Session Data

The `ValkeySessionManager` exposes methods for all CRUD operations. You don't need to touch Valkey directly for most tasks:

```python
import valkey
from strands_valkey_session_manager import ValkeySessionManager

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)
sm = ValkeySessionManager(session_id="user-42", client=client)

# Read session metadata
session = sm.read_session("user-42")
print(f"Created: {session.created_at}")

# Read agent state
agent_state = sm.read_agent("user-42", "default")
print(f"Message count: {agent_state.conversation_manager_state}")

# List all messages in order
messages = sm.list_messages()
print(f"{len(messages)} messages in session")
for msg in messages:
    text_blocks = [b["text"] for b in msg.content if "text" in b]
    preview = text_blocks[0][:80] if text_blocks else "[tool use/result]"
    print(f"  [{msg.role:9}] {preview}")
```

## Full API Reference

| Method | Description |
|--------|-------------|
| `create_session(session)` | Create a new session record |
| `read_session(session_id)` | Read session metadata |
| `delete_session(session_id)` | Delete a session and all its data |
| `create_agent(session_id, agent)` | Create agent state record |
| `read_agent(session_id, agent_id)` | Read agent state |
| `update_agent(session_id, agent)` | Update agent state |
| `create_message(session_id, agent_id, message)` | Store a new message |
| `read_message(session_id, agent_id, message_id)` | Read a single message by ID |
| `update_message(session_id, agent_id, message)` | Update an existing message |
| `list_messages()` | List all messages for the current session in order |

## How Keys Are Organized

The package uses a hierarchical key scheme. Every key is scoped to a session ID:

```
session:{session_id}                                         # Session metadata
session:{session_id}:agent:{agent_id}                        # Agent state
session:{session_id}:agent:{agent_id}:message:{message_id}   # Individual messages
```
