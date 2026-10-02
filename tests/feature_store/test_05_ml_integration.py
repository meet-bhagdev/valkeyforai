"""Integration tests for Feature Store - ML Integration.

Auto-generated from content markdown. Runs the cookbook code blocks
sequentially against real Valkey and external services.
"""

import pytest


@pytest.mark.asyncio
async def test_05_ml_integration(raw_client):
    """Run all code blocks from: ML Integration."""

    # --- Block 1 ---
    import numpy as np
    from src import ValkeyFeatureStore, Entity, FeatureView, Feature, FeatureType

    # Setup store (same as Cookbook 01)
    store = ValkeyFeatureStore(host="localhost", port=6379)

    user = Entity(name="user", join_keys=["user_id"])
    risk_features = FeatureView(
        name="user_risk_profile",
        entity=user,
        features=[
            Feature("txn_count_1h", FeatureType.INT),
            Feature("avg_txn_amount", FeatureType.FLOAT),
            Feature("unique_merchants_24h", FeatureType.INT),
            Feature("fraud_score", FeatureType.FLOAT),
        ],
        ttl=86400,
    )
    store.register(risk_features)

    # Seed some features
    store.write("user_risk_profile", "user_001", {
        "txn_count_1h": 12,
        "avg_txn_amount": 85.50,
        "unique_merchants_24h": 4,
        "fraud_score": 0.15,
    })

    # ── Inference Time ─────────────────────────────────────────────────

    def predict_fraud(user_id: str) -> dict:
        """Fetch features from Valkey and run fraud prediction."""

        # 1. Fetch features (~0.1ms)
        features = store.read(
            "user_risk_profile",
            user_id,
            ["txn_count_1h", "avg_txn_amount", "unique_merchants_24h"],
        )

        if not features:
            return {"error": "No features found"}

        # 2. Build NumPy feature vector
        vector = np.array([[
            features["txn_count_1h"],
            features["avg_txn_amount"],
            features["unique_merchants_24h"],
        ]])

        # 3. Run model (replace with your trained model)
        # prediction = model.predict_proba(vector)[0][1]
        # For demo, use a simple heuristic:
        score = 0.1
        if features["txn_count_1h"] > 10: score += 0.3
        if features["avg_txn_amount"] > 200: score += 0.2
        if features["unique_merchants_24h"] > 8: score += 0.2

        return {
            "user_id": user_id,
            "fraud_probability": round(score, 3),
            "is_fraud": score > 0.5,
            "features_used": features,
        }

    result = predict_fraud("user_001")
    print(result)
    # {'user_id': 'user_001', 'fraud_probability': 0.4, 'is_fraud': False,
    #  'features_used': {'txn_count_1h': 12, 'avg_txn_amount': 85.5, ...}}

    # --- Block 2 ---
    # Register item features
    item = Entity(name="item", join_keys=["item_id"])
    item_features = FeatureView(
        name="item_catalog",
        entity=item,
        features=[
            Feature("price", FeatureType.FLOAT),
            Feature("category", FeatureType.STRING),
            Feature("popularity", FeatureType.FLOAT),
        ],
        ttl=86400,
    )
    store.register(item_features)

    # Write item features
    store.write("item_catalog", "item_042", {
        "price": 29.99,
        "category": "electronics",
        "popularity": 0.85,
    })

    # ── Recommendation inference ──────────────────────────────────────

    def score_item_for_user(user_id: str, item_id: str) -> float:
        """Score how likely a user is to click on an item."""

        # Fetch user features
        user_feats = store.read("user_risk_profile", user_id,
                                ["avg_txn_amount"])

        # Fetch item features
        item_feats = store.read("item_catalog", item_id,
                                ["price", "popularity"])

        if not user_feats or not item_feats:
            return 0.0

        # Simple scoring: users who spend more prefer pricier items
        price_affinity = min(1.0, user_feats["avg_txn_amount"] / (item_feats["price"] * 10))
        score = price_affinity * 0.4 + item_feats["popularity"] * 0.6

        return round(score, 3)

    # Score candidates
    items = ["item_042", "item_043", "item_044"]
    scores = [(item_id, score_item_for_user("user_001", item_id)) for item_id in items]
    ranked = sorted(scores, key=lambda x: x[1], reverse=True)
    print(ranked)

    # --- Block 3 ---
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    import time

    app = FastAPI()

    # Initialize store once at startup
    store = ValkeyFeatureStore(host="localhost", port=6379)
    # ... register feature views ...

    class PredictionResponse(BaseModel):
        user_id: str
        fraud_probability: float
        is_fraud: bool
        latency_ms: float

    @app.get("/predict/fraud/{user_id}")
    async def predict_fraud_endpoint(user_id: str):
        start = time.time()

        # Fetch features from Valkey
        features = store.read(
            "user_risk_profile", user_id,
            ["txn_count_1h", "avg_txn_amount", "unique_merchants_24h"],
        )

        if not features:
            raise HTTPException(status_code=404, detail="No features found")

        # Run model prediction
        score = 0.1
        if features.get("txn_count_1h", 0) > 10: score += 0.3
        if features.get("avg_txn_amount", 0) > 200: score += 0.2
        if features.get("unique_merchants_24h", 0) > 8: score += 0.2

        elapsed = (time.time() - start) * 1000

        return PredictionResponse(
            user_id=user_id,
            fraud_probability=round(score, 3),
            is_fraud=score > 0.5,
            latency_ms=round(elapsed, 2),
        )

    # Run: uvicorn app:app --reload
    # Test: curl localhost:8000/predict/fraud/user_001

    # --- Block 4 ---
    def build_personalized_prompt(user_id: str, question: str) -> str:
        """Fetch user features and build a personalized LLM prompt."""

        # Fetch user context from Valkey
        features = store.read("user_risk_profile", user_id)

        if features:
            context = f"""User context:
    - Average transaction: ${features.get('avg_txn_amount', 'unknown')}
    - Transaction frequency: {features.get('txn_count_1h', 'unknown')}/hour
    - Merchant diversity: {features.get('unique_merchants_24h', 'unknown')} unique merchants"""
        else:
            context = "No user context available."

        prompt = f"""{context}

    User question: {question}

    Please provide a personalized response based on the user's profile."""

        return prompt

    # Usage
    prompt = build_personalized_prompt("user_001", "Should I upgrade my account?")
    print(prompt)
    # Pass to your LLM: response = openai.chat(prompt)

    # --- Block 5 ---
    # Define a view with vector features
    embedding_view = FeatureView(
        name="user_embeddings",
        entity=user,
        features=[
            Feature("embedding", FeatureType.VECTOR),
            Feature("model_version", FeatureType.STRING),
        ],
        ttl=604800,  # 7 days
    )
    store.register(embedding_view)

    # Write an embedding vector
    store.write("user_embeddings", "user_001", {
        "embedding": [0.1, 0.23, -0.05, 0.87, 0.42],  # list → comma-separated
        "model_version": "v2.1",
    })

    # Read embedding back (auto-deserializes to list of floats)
    result = store.read("user_embeddings", "user_001")
    print(result["embedding"])
    # [0.1, 0.23, -0.05, 0.87, 0.42]

    # Convert to NumPy for model input
    embedding = np.array(result["embedding"])
    print(embedding.shape)
    # (5,)

