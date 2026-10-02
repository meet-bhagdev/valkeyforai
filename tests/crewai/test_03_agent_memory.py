"""Integration tests for CrewAI - Agent Memory.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_03_agent_memory(client):
    """Run all code blocks from: Agent Memory."""

    # --- Block 1 ---
    import boto3
    from crewai.memory.unified_memory import Memory
    from valkey_storage import ValkeyStorage

    def build_memory() -> Memory:
        session = boto3.Session(region_name="us-west-2")
        return Memory(
            storage=ValkeyStorage(),
            llm="bedrock/anthropic.claude-3-haiku-20240307-v1:0",
            embedder={
                "provider": "amazon-bedrock",
                "config": {
                    "model_name": "amazon.titan-embed-text-v1",
                    "session": session,
                },
            },
        )

    # --- Block 2 ---
    from crewai import Agent, Crew, Task

    memory = build_memory()

    reviewer = Agent(
        role="Senior Code Reviewer",
        goal="Review code for quality, security, and best practices",
        backstory="You are an experienced engineer who has reviewed thousands of PRs.",
        memory=True,
        verbose=True,
    )

    # --- Block 3 ---
    # First crew run - agent learns patterns
    learn_task = Task(
        description="""Review this code and remember the patterns you find:
        
        def get_user(id):
            user = db.query(f"SELECT * FROM users WHERE id = {id}")
            return user
        """,
        expected_output="Code review with identified patterns",
        agent=reviewer,
    )

    crew = Crew(
        agents=[reviewer],
        tasks=[learn_task],
        memory=memory,
        verbose=True,
    )

    result = crew.kickoff()
    print(result)
    # Agent identifies: SQL injection risk, no input validation, no error handling

    # --- Block 4 ---
    JSON.SET memory:7f3a-b2c1 $ '{"content":"SQL injection risk in get_user...","scope":"/code-review","embedding":[0.12,-0.45,...],...}'
    EXPIRE memory:7f3a-b2c1 3600

    # --- Block 5 ---
    # Later crew run - agent recalls what it learned
    recall_task = Task(
        description="""Review this new code. Use your memory of past reviews:
        
        def delete_account(user_id):
            db.execute(f"DELETE FROM accounts WHERE user_id = {user_id}")
            return {"status": "deleted"}
        """,
        expected_output="Code review informed by past patterns",
        agent=reviewer,
    )

    crew2 = Crew(
        agents=[reviewer],
        tasks=[recall_task],
        memory=memory,  # Same memory - recalls from Valkey
        verbose=True,
    )

    result2 = crew2.kickoff()
    print(result2)
    # Agent recalls the SQL injection pattern from the first review!
    # "I've seen this pattern before - f-string SQL is vulnerable to injection..."

