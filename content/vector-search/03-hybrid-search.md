## Why Hybrid Search?

Pure vector search returns the most similar items globally. But often you need to filter first — "find similar articles, but only in the _tech_ category" or "similar products under $50." Hybrid search lets you combine vector KNN with traditional filters in a single query.

## Step 1: Create an Index with Multiple Field Types
    
    
    import redis
    import numpy as np
    
    client = redis.Redis(host="localhost", port=6379)
    
    def vec_to_bytes(vec):
        return np.array(vec, dtype=np.float32).tobytes()
    
    # Create index with VECTOR + TAG + NUMERIC + TEXT fields
    try:
        client.execute_command(
            "FT.CREATE", "articles_idx",
            "SCHEMA",
            "title", "TAG",
            "category", "TAG",
            "year", "NUMERIC",
            "embedding", "VECTOR", "HNSW", "6",
            "TYPE", "FLOAT32",
            "DIM", "4",
            "DISTANCE_METRIC", "COSINE",
        )
        print("Index created with TEXT + TAG + NUMERIC + VECTOR")
    except redis.ResponseError as e:
        print(f"Index exists: {e}")

## Step 2: Store Documents with Metadata
    
    
    # Articles with category tags, year, and embeddings
    articles = [
        {"key": "art:1", "title": "Introduction to Vector Databases",
         "category": "tech", "year": "2024",
         "embedding": vec_to_bytes([0.9, 0.1, 0.2, 0.3])},
        {"key": "art:2", "title": "Deep Learning for NLP",
         "category": "tech", "year": "2023",
         "embedding": vec_to_bytes([0.8, 0.15, 0.25, 0.35])},
        {"key": "art:3", "title": "Cooking with AI-Generated Recipes",
         "category": "food", "year": "2024",
         "embedding": vec_to_bytes([0.1, 0.8, 0.6, 0.2])},
        {"key": "art:4", "title": "Scaling Valkey for Production",
         "category": "tech", "year": "2025",
         "embedding": vec_to_bytes([0.85, 0.12, 0.18, 0.4])},
        {"key": "art:5", "title": "Healthy Meal Planning with ML",
         "category": "food", "year": "2025",
         "embedding": vec_to_bytes([0.15, 0.75, 0.55, 0.25])},
        {"key": "art:6", "title": "Financial Forecasting with AI",
         "category": "finance", "year": "2024",
         "embedding": vec_to_bytes([0.3, 0.4, 0.1, 0.9])},
    ]
    
    for art in articles:
        key = art.pop("key")
        client.hset(key, mapping=art)
    print(f"Stored {len(articles)} articles")

## Step 3: TAG Filter + Vector Search

Find similar articles, but **only in the "tech" category** :
    
    
    query_vec = vec_to_bytes([0.88, 0.1, 0.2, 0.35])
    
    # TAG filter: @category:{tech}
    # Combined with KNN: @category:{tech}=>[KNN 3 @embedding $query_vec]
    results = client.execute_command(
        "FT.SEARCH", "articles_idx",
        "@category:{tech}=>[KNN 3 @embedding $query_vec]",
        "PARAMS", "2", "query_vec", query_vec,
        "DIALECT", "2",
    )
    
    print(f"Tech articles (KNN): {results[0]} results")
    for i in range(1, len(results), 2):
        fields = results[i + 1]
        fd = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
        print(f"  {results[i]}: {fd.get('title')} [{fd.get('category')}]")
    
    # Only returns tech articles — food and finance are excluded!

## Step 4: NUMERIC Range + Vector Search

Find similar articles from **2024 or later** :
    
    
    # NUMERIC filter: @year:[2024 +inf]
    results = client.execute_command(
        "FT.SEARCH", "articles_idx",
        "@year:[2024 +inf]=>[KNN 3 @embedding $query_vec]",
        "PARAMS", "2", "query_vec", query_vec,
        "DIALECT", "2",
    )
    
    print(f"\nArticles from 2024+: {results[0]} results")
    for i in range(1, len(results), 2):
        fields = results[i + 1]
        fd = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
        print(f"  {results[i]}: {fd.get('title')} ({fd.get('year')})")

## Step 5: Combined TAG + NUMERIC + Vector

Find similar **tech articles from 2024+** :
    
    
    # Combine multiple filters
    results = client.execute_command(
        "FT.SEARCH", "articles_idx",
        "(@category:{tech} @year:[2024 +inf])=>[KNN 3 @embedding $query_vec]",
        "PARAMS", "2", "query_vec", query_vec,
        "DIALECT", "2",
    )
    
    print(f"\nTech articles from 2024+: {results[0]} results")
    for i in range(1, len(results), 2):
        fields = results[i + 1]
        fd = {fields[j]: fields[j+1] for j in range(0, len(fields), 2)}
        print(f"  {results[i]}: {fd.get('title')} [{fd.get('category')}, {fd.get('year')}]")

## Filter Syntax Reference

Filter Type| Syntax| Example  
---|---|---  
TAG exact| `@field:{value}`| `@category:{tech}`  
TAG OR| `@field:{val1|val2}`| `@category:{tech|science}`  
NUMERIC range| `@field:[min max]`| `@year:[2024 2025]`  
NUMERIC ≥| `@field:[min +inf]`| `@year:[2024 +inf]`  
NUMERIC ≤| `@field:[-inf max]`| `@price:[-inf 50]`  
Combined AND| `(@filter1 @filter2)`| `(@category:{tech} @year:[2024 +inf])`  
  
**Filter + KNN pattern:** `"FILTER_EXPRESSION=>[KNN k @vector $param]"`. The filter runs first (pre-filtering), then KNN finds the nearest neighbors within the filtered set.