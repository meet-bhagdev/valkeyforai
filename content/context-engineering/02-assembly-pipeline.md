## The Context Assembly Function

Before every LLM call, an agent needs to assemble context from multiple sources. This function is the core of context engineering — it gathers everything the LLM needs into a structured prompt.

```python
import valkey
import json
import struct
import time

client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)
client_bin = valkey.Valkey(host="localhost", port=6379, decode_responses=False)

def assemble_context(user_id: str, session_id: str, agent_id: str, current_message: str) -> list:
    """Assemble complete context for an LLM call from all 5 sources in Valkey."""
    messages = []

    # 1. System instructions (broadest context)
    config = client.hgetall(f"agent:config:{agent_id}")
    if config:
        system_prompt = f"{config.get('role', '')}\n\nConstraints: {config.get('constraints', '')}\nFormat: {config.get('output_format', '')}"
        messages.append({"role": "system", "content": system_prompt})

    # 2. User memory (cross-session preferences)
    memories = client.hgetall(f"memory:{user_id}")
    if memories:
        mem_str = "\n".join(f"- {k}: {v}" for k, v in memories.items())
        messages.append({"role": "system", "content": f"User context:\n{mem_str}"})

    # 3. Retrieved knowledge (RAG — would use FT.SEARCH in production)
    # Simplified here; see the Vector Search cookbook for full implementation
    kb_results = client.lrange(f"kb:results:{session_id}", 0, -1)
    if kb_results:
        docs = [json.loads(d) for d in kb_results]
        kb_str = "\n\n".join(f"[{d.get('title', 'Doc')}]: {d.get('content', '')}" for d in docs)
        messages.append({"role": "system", "content": f"Relevant knowledge:\n{kb_str}"})

    # 4. Conversation history (recent turns)
    history = client.lrange(f"chat:{session_id}", -10, -1)
    for raw in history:
        msg = json.loads(raw)
        messages.append({"role": msg["role"], "content": msg["content"]})

    # 5. Tool outputs from current session
    tool_keys = client.keys(f"tool:{session_id}:step_*")
    for key in sorted(tool_keys):
        data = client.hgetall(key)
        messages.append({
            "role": "system",
            "content": f"Tool '{data.get('tool', 'unknown')}' returned: {data.get('result', '{}')}",
        })

    # 6. Current user message (most specific)
    messages.append({"role": "user", "content": current_message})

    return messages
```

## Token Budgeting

Context windows have limits. You need to budget tokens across sources:

```python
def budget_context(messages: list, max_tokens: int = 8000) -> list:
    """Trim context to fit within the token budget.
    
    Simple heuristic: ~4 chars per token for English text.
    In production, use tiktoken for accurate counting.
    """
    CHARS_PER_TOKEN = 4
    max_chars = max_tokens * CHARS_PER_TOKEN

    total = sum(len(m["content"]) for m in messages)
    if total <= max_chars:
        return messages  # Fits already

    # Priority: keep system prompt + current message, trim history from oldest
    system_msgs = [m for m in messages if m["role"] == "system"]
    user_msgs = [m for m in messages if m["role"] != "system"]

    # Always keep the last user message
    current = user_msgs[-1:]
    history = user_msgs[:-1]

    # Trim history from the oldest until it fits
    budget_remaining = max_chars - sum(len(m["content"]) for m in system_msgs + current)
    trimmed_history = []
    for msg in reversed(history):
        if budget_remaining - len(msg["content"]) > 0:
            trimmed_history.insert(0, msg)
            budget_remaining -= len(msg["content"])
        else:
            break

    return system_msgs + trimmed_history + current
```

## Putting It Together

```python
# Setup: store some context
client.hset("agent:config:demo_agent", mapping={
    "role": "You are a helpful AI assistant.",
    "constraints": "Be concise and accurate.",
    "output_format": "Plain text.",
})

client.hset("memory:user_42", mapping={
    "name": "Bob",
    "preferred_language": "English",
    "tier": "free",
})

# Add conversation
for msg in [
    ("user", "Hi, I need help with my account"),
    ("assistant", "Sure! What do you need help with?"),
    ("user", "I want to upgrade to premium"),
]:
    data = json.dumps({"role": msg[0], "content": msg[1], "ts": time.time()})
    client.rpush("chat:sess_42", data)
client.expire("chat:sess_42", 1800)

# Store a tool result
client.hset("tool:sess_42:step_1", mapping={
    "tool": "check_account",
    "result": json.dumps({"plan": "free", "eligible_upgrade": True}),
    "timestamp": str(time.time()),
})
client.expire("tool:sess_42:step_1", 3600)

# Assemble context
context = assemble_context("user_42", "sess_42", "demo_agent", "How much does premium cost?")
budgeted = budget_context(context, max_tokens=4000)

print(f"Assembled {len(context)} messages, budgeted to {len(budgeted)}")
for msg in budgeted:
    print(f"  [{msg['role']}] {msg['content'][:80]}...")
```

## Context Assembly Flow

| Step | Source | Valkey Command | Purpose |
|------|--------|---------------|---------|
| 1 | System config | `HGETALL agent:config:{id}` | Agent role + constraints |
| 2 | User memory | `HGETALL memory:{user_id}` | Preferences, history |
| 3 | Knowledge base | `FT.SEARCH` or `LRANGE` | Retrieved docs (RAG) |
| 4 | Chat history | `LRANGE chat:{session} -10 -1` | Recent conversation |
| 5 | Tool outputs | `HGETALL tool:{session}:step_*` | Function call results |
| 6 | Current message | (from input) | What the user just said |

> **Key insight from Philipp Schmid (Google DeepMind):** "Context engineering is a system, not a string. Context isn't just a static prompt template — it's the output of a system that runs before the main LLM call."
