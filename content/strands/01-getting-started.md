Strands agents are stateless by default. Without a session manager, every conversation starts from scratch. Valkey stores the full conversation history, agent state, and tool results so your agent remembers context across requests and can resume interrupted workflows.

The `strands-valkey-session-manager` package provides a ready-to-use `ValkeySessionManager` that plugs directly into Strands' `Agent(session_manager=...)` parameter. No custom implementation needed.

## What Gets Stored

The session manager persists three types of data to Valkey:

| Data | Key Pattern | Description |
|------|------------|-------------|
| Session Record | `session:{id}` | Top-level record for a conversation. Tracks when the session was created and last updated. |
| Agent State | `session:{id}:agent:{agent_id}` | Per-agent record within a session. Tracks message count and interrupt state - used to resume the agent exactly where it left off. |
| Conversation Messages | `session:{id}:agent:{agent_id}:message:{msg_id}` | A single turn in the conversation. Stores the role (user or assistant), content, any tool calls or results, and a timestamp. |

## Prerequisites

- Docker installed
- Python 3.10+
- An LLM provider configured (Strands supports Amazon Bedrock, Anthropic, OpenAI, and others)

## Step 1: Start Valkey

```bash
docker run -d --name valkey -p 6379:6379 valkey/valkey-bundle:latest
```

```bash
docker exec valkey valkey-cli PING
# PONG
```

## Step 2: Install Dependencies

```bash
pip install strands-agents strands-agents-tools
pip install valkey
pip install strands-valkey-session-manager
```

**Package:** `strands-valkey-session-manager` is a community package. Source: [GitHub](https://github.com/jeromevdl/strands-valkey-session-manager) - Docs: [strandsagents.com](https://strandsagents.com/docs/community/session-managers/strands-valkey-session-manager/)

## Step 3: Connect to Valkey

```python
import valkey
from strands_valkey_session_manager import ValkeySessionManager

# Connect to Valkey
client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

# Create the session manager - one per session
session_manager = ValkeySessionManager(
    session_id="user-42",
    client=client,
)
```

## Step 4: Give Your Agent Memory

```python
from strands import Agent

agent = Agent(
    system_prompt="You are a helpful assistant.",
    session_manager=session_manager,
)

# Strands automatically persists every turn to Valkey
response = agent("My name is Alex and I'm building a RAG pipeline.")
print(response)
```
