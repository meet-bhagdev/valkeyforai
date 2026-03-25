#!/usr/bin/env python3
"""
Test script for Strands + Valkey cookbooks.
Exercises code from cookbooks 01, 02, and 03 against a local Valkey instance.
No LLM needed — uses the ValkeySessionManager API directly.
"""

import sys
import uuid
import valkey
from strands_valkey_session_manager import ValkeySessionManager
from strands.types.session import Session, SessionType, SessionAgent, SessionMessage
from strands.types.content import Message

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
results = []


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append(condition)
    msg = f"  {status} {name}"
    if detail and not condition:
        msg += f"  — {detail}"
    print(msg)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
print("\n🔧 Connecting to Valkey on localhost:6379 ...")
client = valkey.Valkey(host="localhost", port=6379, decode_responses=True)

try:
    pong = client.ping()
    check("Valkey PING", pong is True)
except Exception as e:
    print(f"  {FAIL} Cannot connect to Valkey: {e}")
    sys.exit(1)

SESSION_ID = f"test-{uuid.uuid4().hex[:8]}"
print(f"\n📋 Using session ID: {SESSION_ID}")

# ---------------------------------------------------------------------------
# Cookbook 01 — Getting Started
# ---------------------------------------------------------------------------
print("\n── Cookbook 01: Getting Started ──")

# Constructor auto-creates the session in Valkey if it doesn't exist
sm = ValkeySessionManager(session_id=SESSION_ID, client=client)
check("ValkeySessionManager created", sm is not None)
check("session_id matches", sm.session_id == SESSION_ID)

# Session was auto-created by constructor
session = sm.read_session(SESSION_ID)
check("Session auto-created in Valkey", session is not None)
check("Session ID correct", session.session_id == SESSION_ID)

# ---------------------------------------------------------------------------
# Cookbook 02 — Managing Session Data
# ---------------------------------------------------------------------------
print("\n── Cookbook 02: Managing Session Data ──")

# Create agent state
agent = SessionAgent(
    agent_id="default",
    state={},
    conversation_manager_state={"message_count": 0},
)
sm.create_agent(SESSION_ID, agent)

agent_back = sm.read_agent(SESSION_ID, "default")
check("Agent state created & read", agent_back is not None)
check("Agent ID is 'default'", agent_back.agent_id == "default")

# Create messages (Conversation Messages)
user_msg = SessionMessage(
    message=Message(role="user", content=[{"text": "My name is Alex and I'm building a RAG pipeline."}]),
    message_id=0,
)
sm.create_message(SESSION_ID, "default", user_msg)

assistant_msg = SessionMessage(
    message=Message(role="assistant", content=[{"text": "Nice to meet you, Alex! I can help with RAG pipelines."}]),
    message_id=1,
)
sm.create_message(SESSION_ID, "default", assistant_msg)

messages = sm.list_messages(SESSION_ID, "default")
check("Two messages stored", len(messages) == 2, f"got {len(messages)}")

first_role = messages[0].message["role"] if isinstance(messages[0].message, dict) else messages[0].message.get("role", getattr(messages[0], "role", None))
check("First message is user role", first_role == "user", f"got {first_role}")

# Verify keys exist (How Keys Are Organized)
keys = client.keys(f"session:{SESSION_ID}*")
check("Valkey keys created (>=3)", len(keys) >= 3, f"found {len(keys)} keys")

print("\n  Keys in Valkey:")
for k in sorted(keys):
    print(f"    {k}")

# Read and Update Session Data (API section)
session_read = sm.read_session(SESSION_ID)
check("read_session returns data", session_read.session_id == SESSION_ID)

agent_read = sm.read_agent(SESSION_ID, "default")
check("read_agent returns data", agent_read.agent_id == "default")

# ---------------------------------------------------------------------------
# Cookbook 02 — Pick Up Where You Left Off
# ---------------------------------------------------------------------------
print("\n── Cookbook 02: Resume Session ──")

# New manager instance, same session_id — should reload everything
sm2 = ValkeySessionManager(session_id=SESSION_ID, client=client)
check("New manager reuses existing session", not sm2._is_new_session)

resumed = sm2.list_messages(SESSION_ID, "default")
check("Resumed session has same messages", len(resumed) == 2)

# ---------------------------------------------------------------------------
# Cookbook 03 — Share a Session Across Multiple Agents
# ---------------------------------------------------------------------------
print("\n── Cookbook 03: Multi-Agent Session ──")

MULTI_ID = f"multi-{uuid.uuid4().hex[:8]}"

sm_r = ValkeySessionManager(session_id=MULTI_ID, client=client)

# Create two different agents under the same session
researcher = SessionAgent(agent_id="researcher", state={}, conversation_manager_state={"message_count": 0})
writer = SessionAgent(agent_id="writer", state={}, conversation_manager_state={"message_count": 0})
sm_r.create_agent(MULTI_ID, researcher)
sm_r.create_agent(MULTI_ID, writer)

sm_r.create_message(MULTI_ID, "researcher", SessionMessage(
    message=Message(role="user", content=[{"text": "Research Valkey for AI workloads."}]),
    message_id=0,
))
sm_r.create_message(MULTI_ID, "writer", SessionMessage(
    message=Message(role="user", content=[{"text": "Write a blog intro about Valkey."}]),
    message_id=0,
))

multi_keys = client.keys(f"session:{MULTI_ID}*")
has_researcher = any("agent:researcher" in k for k in multi_keys)
has_writer = any("agent:writer" in k for k in multi_keys)
check("Researcher agent keys exist", has_researcher)
check("Writer agent keys exist", has_writer)
check("Both agents share same session", has_researcher and has_writer)

# ---------------------------------------------------------------------------
# Cookbook 03 — Clean Up on Logout
# ---------------------------------------------------------------------------
print("\n── Cookbook 03: Cleanup ──")

sm.delete_session(SESSION_ID)
leftover = client.keys(f"session:{SESSION_ID}*")
check("delete_session removes all keys", len(leftover) == 0, f"{len(leftover)} keys remain")

sm_r.delete_session(MULTI_ID)
leftover2 = client.keys(f"session:{MULTI_ID}*")
check("Multi-agent session cleaned up", len(leftover2) == 0)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
passed = sum(results)
total = len(results)
print(f"\n{'='*50}")
if passed == total:
    print(f"  🎉 All {total} checks passed!")
else:
    print(f"  ⚠️  {passed}/{total} checks passed, {total - passed} failed")
print(f"{'='*50}\n")

sys.exit(0 if passed == total else 1)
