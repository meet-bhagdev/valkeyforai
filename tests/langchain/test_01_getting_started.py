"""Integration tests for LangChain - Getting Started with LangChain + Valkey.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with LangChain + Valkey."""

    # --- Block 1 ---
    from langgraph.graph import StateGraph, MessagesState
    from langgraph_checkpoint_aws import ValkeySaver
    from langchain_aws import ChatBedrockConverse
    from langchain_core.messages import HumanMessage


    # 1. Create a simple chatbot graph
    model = ChatBedrockConverse(
        model="us.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name="us-west-2",
    )

    def chatbot(state: MessagesState):
        return {"messages": [model.invoke(state["messages"])]}

    builder = StateGraph(MessagesState)
    builder.add_node("chatbot", chatbot)
    builder.set_entry_point("chatbot")
    builder.set_finish_point("chatbot")

    # 2. Compile with ValkeySaver - this is the key line
    with ValkeySaver.from_conn_string(
        "valkey://localhost:6379",
        ttl_seconds=3600,
    ) as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)

        # 3. Invoke with a thread ID
        config = {"configurable": {"thread_id": "session-1"}}
        result = graph.invoke(
            {"messages": [HumanMessage(content="What is Valkey?")]},
            config,
        )
        print(result["messages"][-1].content)

        # 4. Continue the conversation - state is persisted!
        result = graph.invoke(
            {"messages": [HumanMessage(content="How fast is it?")]},
            config,
        )
        # The agent remembers the previous message about Valkey
        print(result["messages"][-1].content)

    # --- Block 2 ---
    # In a NEW Python process:
    with ValkeySaver.from_conn_string("valkey://localhost:6379") as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "session-1"}}

        # List checkpoints for this thread
        for cp in checkpointer.list(config):
            print(cp.metadata)  # Shows previous conversation

