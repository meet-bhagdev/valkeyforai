## The Architecture
    
    
    # 1. Embed documents with OpenAI → store in Valkey
    # 2. User query → embed query → FT.SEARCH KNN → return matches
    #
    #  Document → OpenAI embed → HSET doc:1 embedding [binary] content "..."
    #  Query    → OpenAI embed → FT.SEARCH idx "*=>[KNN 5 @embedding $vec]"

## Step 1: Setup
    
    
    pip install redis openai numpy
    
    
    import redis
    import numpy as np
    from openai import OpenAI
    
    client = redis.Redis(host="localhost", port=6379)
    openai_client = OpenAI()  # Uses OPENAI_API_KEY env var
    
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIM = 1536  # text-embedding-3-small outputs 1536 dimensions

## Step 2: Create Index for 1536-dim Vectors
    
    
    try:
        client.execute_command(
            "FT.CREATE", "semantic_idx",
            "SCHEMA",
            "content", "TAG",
            "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", str(EMBEDDING_DIM),
            "DISTANCE_METRIC", "COSINE",
        )
        print("Index created")
    except redis.ResponseError:
        print("Index already exists")

## Step 3: Embed and Store Documents
    
    
    def get_embedding(text: str) -> bytes:
        """Get embedding from OpenAI and return as binary FLOAT32."""
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        vec = response.data[0].embedding  # list of 1536 floats
        return np.array(vec, dtype=np.float32).tobytes()
    
    # Sample documents
    docs = [
        "Valkey is an open-source in-memory data store forked from Redis",
        "Vector similarity search finds documents by semantic meaning",
        "Machine learning models convert text into numerical embeddings",
        "Python is the most popular language for AI development",
        "HNSW algorithm provides fast approximate nearest neighbor search",
        "Kubernetes orchestrates containerized applications at scale",
        "LLMs like GPT-4 generate human-like text responses",
        "Rate limiting protects APIs from excessive usage",
    ]
    
    # Embed and store each document
    for i, text in enumerate(docs):
        embedding_bytes = get_embedding(text)
        client.hset(f"doc:{i}", mapping={
            "content": text,
            "embedding": embedding_bytes,
        })
        print(f"Stored doc:{i}: {text[:50]}...")
    
    print(f"\nStored {len(docs)} documents with embeddings")

## Step 4: Search by Meaning
    
    
    def semantic_search(query: str, k: int = 3):
        """Search for documents semantically similar to the query."""
    
        # Embed the query
        query_vec = get_embedding(query)
    
        # KNN search
        results = client.execute_command(
            "FT.SEARCH", "semantic_idx",
            f"*=>[KNN {k} @embedding $query_vec]",
            "PARAMS", "2", "query_vec", query_vec,
            "DIALECT", "2",
        )
    
        # Parse results
        matches = []
        for i in range(1, len(results), 2):
            doc_key = results[i]
            fields = results[i + 1]
            field_dict = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
            matches.append({
                "key": doc_key,
                "content": field_dict.get("content", ""),
                "score": field_dict.get("__embedding_score", "N/A"),
            })
        return matches
    
    # Try different queries
    queries = [
        "What is Valkey?",
        "How do I find similar documents?",
        "Tell me about large language models",
    ]
    
    for q in queries:
        print(f"\nQuery: '{q}'")
        for m in semantic_search(q, k=2):
            print(f"  → {m['content']} (score: {m['score']})")

**Expected output:**
    
    
    Query: 'What is Valkey?'
      → Valkey is an open-source in-memory data store forked from Redis (score: 0.15)
      → Vector similarity search finds documents by semantic meaning (score: 0.42)
    
    Query: 'How do I find similar documents?'
      → Vector similarity search finds documents by semantic meaning (score: 0.18)
      → HNSW algorithm provides fast approximate nearest neighbor search (score: 0.35)
    
    Query: 'Tell me about large language models'
      → LLMs like GPT-4 generate human-like text responses (score: 0.12)
      → Machine learning models convert text into numerical embeddings (score: 0.28)

## Distance Metrics

Metric| Best For| Range| Lower = Better?  
---|---|---|---  
`COSINE`| Normalized embeddings (OpenAI, etc.)| 0 to 2| Yes  
`L2`| Euclidean distance| 0 to ∞| Yes  
`IP`| Inner product (dot product)| -∞ to ∞| No (higher = more similar)  
  
**Use COSINE for OpenAI embeddings.** OpenAI's embeddings are normalized, so cosine similarity is the correct metric. A score of 0 = identical, 2 = opposite.