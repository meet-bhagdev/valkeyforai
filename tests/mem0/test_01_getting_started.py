"""Integration tests for Mem0 - Getting Started with Mem0 + Valkey.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_01_getting_started(client):
    """Run all code blocks from: Getting Started with Mem0 + Valkey."""

    # --- Block 1 ---
    # Add memories from a conversation
    messages = [
        {"role": "user", "content": "I love Italian food, especially pasta carbonara."},
        {"role": "assistant", "content": "Great choice! Carbonara is a classic Roman dish."},
    ]
    result = memory.add(messages, user_id="user_001")
    print(f"Added: {result}")

    # Add more context
    messages2 = [
        {"role": "user", "content": "I'm allergic to shellfish and prefer spicy food."},
        {"role": "assistant", "content": "Noted! I'll keep that in mind for recommendations."},
    ]
    memory.add(messages2, user_id="user_001")

    # --- Block 2 ---
    # Search for relevant memories
    results = memory.search(
        query="What food does this user like?",
        user_id="user_001",
        limit=3,
    )

    for entry in results["results"]:
        print(f"Memory: {entry['memory']}")
        print(f"Score: {entry.get('score', 'N/A')}\n")

    # Output:
    # Memory: Loves Italian food, especially pasta carbonara
    # Score: 0.87
    # Memory: Allergic to shellfish, prefers spicy food
    # Score: 0.62

    # --- Block 3 ---
    # Retrieve all memories for a user
    all_memories = memory.get_all(user_id="user_001")
    for m in all_memories["results"]:
        print(f"  - {m['memory']}")

    # --- Block 4 ---
    from openai import OpenAI

    openai_client = OpenAI()

    def chat_with_memory(message: str, user_id: str) -> str:
        # 1. Retrieve relevant memories
        relevant = memory.search(query=message, user_id=user_id, limit=3)
        memories_str = "\n".join(
            f"- {entry['memory']}" for entry in relevant["results"]
        )

        # 2. Build prompt with memories
        system = f"You are a helpful AI. Use these memories about the user:\n{memories_str}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ]

        # 3. Generate response
        response = openai_client.chat.completions.create(
            model="gpt-4", messages=messages,
        )
        answer = response.choices[0].message.content

        # 4. Save new memories from this conversation
        memory.add(
            [{"role": "user", "content": message},
             {"role": "assistant", "content": answer}],
            user_id=user_id,
        )
        return answer

    # Usage
    response = chat_with_memory("Recommend me a restaurant", "user_001")
    print(response)
    # Will recommend Italian restaurants, avoid shellfish, suggest spicy options!

