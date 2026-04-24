"""Integration tests for Pub/Sub & Streaming - Streaming LLM Tokens.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


def test_02_streaming_llm_tokens(client):
    """Run all code blocks from: Streaming LLM Tokens."""

    # --- Block 1 ---
    import json
    import time
    import uuid

    client = client

    def stream_llm_response(prompt: str, request_id: str = None):
        """Simulate an LLM streaming response, publishing each token."""
        request_id = request_id or str(uuid.uuid4())[:8]
        channel = f"llm:stream:{request_id}"

        # Notify clients that streaming has started
        client.publish(channel, json.dumps({
            "type": "start",
            "request_id": request_id,
            "model": "gpt-4",
            "timestamp": time.time(),
        }))

        # Simulate token-by-token streaming
        tokens = ["Valkey", " is", " an", " open", "-source",
                  " in", "-memory", " data", " store", "."]

        for i, token in enumerate(tokens):
            # In production, this would come from the LLM API:
            # for chunk in openai.chat.completions.create(stream=True):
            #     token = chunk.choices[0].delta.content

            client.publish(channel, json.dumps({
                "type": "token",
                "content": token,
                "index": i,
                "timestamp": time.time(),
            }))
            time.sleep(0.05)  # Simulate token delay

        # Notify clients that streaming is complete
        client.publish(channel, json.dumps({
            "type": "end",
            "request_id": request_id,
            "total_tokens": len(tokens),
            "timestamp": time.time(),
        }))

        return request_id

    # Usage
    rid = stream_llm_response("What is Valkey?")
    print(f"Streamed response: {rid}")

    # --- Block 2 ---
    import json

    client = client

    def watch_stream(request_id: str):
        """Subscribe to an LLM response stream and reassemble tokens."""
        pubsub = client.pubsub()
        channel = f"llm:stream:{request_id}"
        pubsub.subscribe(channel)

        full_response = []

        for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data = json.loads(message["data"])

            if data["type"] == "start":
                print(f"Stream started (model: {data['model']})")

            elif data["type"] == "token":
                token = data["content"]
                full_response.append(token)
                print(token, end="", flush=True)  # Print token-by-token

            elif data["type"] == "end":
                print(f"\n--- Complete ({data['total_tokens']} tokens) ---")
                break

        pubsub.unsubscribe(channel)
        return "".join(full_response)

    # Run in another terminal:
    # result = watch_stream("abc123")
    # Output: Valkey is an open-source in-memory data store.

    # --- Block 3 ---
    from openai import OpenAI

    openai_client = OpenAI()

    def stream_openai_to_valkey(prompt: str, request_id: str):
        """Stream from OpenAI API → Valkey Pub/Sub → all subscribers."""
        channel = f"llm:stream:{request_id}"

        client.publish(channel, json.dumps({"type": "start"}))

        stream = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )

        token_count = 0
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                client.publish(channel, json.dumps({
                    "type": "token",
                    "content": content,
                    "index": token_count,
                }))
                token_count += 1

        client.publish(channel, json.dumps({
            "type": "end",
            "total_tokens": token_count,
        }))

