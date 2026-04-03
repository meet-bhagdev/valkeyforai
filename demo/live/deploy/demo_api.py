"""Valkey for AI - Live Demo API with real Bedrock embeddings + LLM"""
import time, hashlib, json, os
from contextlib import asynccontextmanager
import numpy as np
import boto3
import valkey
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

vk = None
bedrock = None

@asynccontextmanager
async def lifespan(app):
    global vk, bedrock
    vk = valkey.Valkey(
        host=os.environ.get("VALKEY_HOST", "localhost"),
        port=int(os.environ.get("VALKEY_PORT", "6379")),
        decode_responses=False,
    )
    vk.ping()
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    yield
    vk.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def embed(text):
    resp = bedrock.invoke_model(modelId="amazon.titan-embed-text-v1", body=json.dumps({"inputText": text}))
    return json.loads(resp["body"].read())["embedding"]

def vec(floats):
    return np.array(floats, dtype=np.float32).tobytes()

def llm(prompt):
    resp = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 300,
                         "system": "You are a helpful technical assistant. Valkey is an open-source, high-performance in-memory data store. It was forked from Redis and is maintained by the Linux Foundation. It supports strings, hashes, lists, sets, sorted sets, streams, and vector search via the valkey-search module. It is used for caching, session storage, real-time analytics, and AI workloads like semantic caching and vector similarity search. Answer concisely.",
                         "messages": [{"role": "user", "content": prompt}]}),
    )
    return json.loads(resp["body"].read())["content"][0]["text"]

def parse_results(results):
    docs = []
    for i in range(1, len(results), 2):
        key = results[i].decode() if isinstance(results[i], bytes) else results[i]
        fields = results[i + 1]
        fd = {}
        for j in range(0, len(fields), 2):
            k = fields[j].decode() if isinstance(fields[j], bytes) else fields[j]
            v = fields[j + 1]
            try: v = v.decode()
            except: pass
            fd[k] = v
        docs.append({"key": key, **{k: v for k, v in fd.items() if k != "embedding"}})
    return docs

SAMPLE_DOCS = [
    ("doc:1", "Valkey is a high-performance in-memory data store forked from Redis, maintained by the Linux Foundation", "tech"),
    ("doc:2", "Vector similarity search uses HNSW indexes to find nearest neighbors in sub-millisecond time", "tech"),
    ("doc:3", "Python is the most popular language for machine learning and data science applications", "tech"),
    ("doc:4", "Pasta carbonara is a classic Roman dish made with eggs, pecorino cheese, guanciale, and black pepper", "food"),
    ("doc:5", "Neural networks learn patterns from data by adjusting weights through backpropagation", "tech"),
    ("doc:6", "Sushi originated as a method of preserving fish in fermented rice in Southeast Asia", "food"),
    ("doc:7", "Kubernetes orchestrates containerized applications across clusters of machines", "tech"),
    ("doc:8", "The FIFA World Cup is the most watched sporting event globally with billions of viewers", "sports"),
]

@app.get("/api/health")
def health():
    t0 = time.perf_counter()
    vk.ping()
    return {"status": "ok", "ping_ms": round((time.perf_counter() - t0) * 1000, 2)}

# --- Vector Search ---

class SearchReq(BaseModel):
    query: str
    k: int = 3

@app.post("/api/vector-search/setup")
def vs_setup():
    try: vk.execute_command("FT.DROPINDEX", "demo:vs_idx")
    except: pass
    for k in vk.keys("demo:doc:*"): vk.delete(k)
    vk.execute_command(
        "FT.CREATE", "demo:vs_idx", "ON", "HASH", "PREFIX", "1", "demo:doc:",
        "SCHEMA", "content", "TAG", "category", "TAG",
        "embedding", "VECTOR", "HNSW", "6", "TYPE", "FLOAT32", "DIM", "1536", "DISTANCE_METRIC", "COSINE",
    )
    cmds = ["FT.CREATE demo:vs_idx ON HASH PREFIX 1 demo:doc: SCHEMA content TAG category TAG embedding VECTOR HNSW 6 TYPE FLOAT32 DIM 1536 DISTANCE_METRIC COSINE"]
    for key, content, cat in SAMPLE_DOCS:
        emb = embed(content)
        vk.hset(f"demo:{key}", mapping={"content": content, "category": cat, "embedding": vec(emb)})
        cmds.append(f'HSET demo:{key} content "{content[:50]}..." category "{cat}" embedding [1536-dim float32]')
    time.sleep(0.5)
    return {"status": "ok", "docs": len(SAMPLE_DOCS), "dim": 1536, "commands": cmds}

@app.post("/api/vector-search/search")
def vs_search(req: SearchReq):
    t0 = time.perf_counter()
    query_emb = embed(req.query)
    embed_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    results = vk.execute_command(
        "FT.SEARCH", "demo:vs_idx", f"*=>[KNN {req.k} @embedding $v]",
        "PARAMS", "2", "v", vec(query_emb), "DIALECT", "2",
    )
    search_ms = (time.perf_counter() - t1) * 1000
    docs = parse_results(results)
    for d in docs:
        d["score"] = round(float(d.pop("__embedding_score", 0)), 6)
    return {
        "count": results[0], "docs": docs,
        "latency": {"embed_ms": round(embed_ms, 1), "search_ms": round(search_ms, 2), "total_ms": round(embed_ms + search_ms, 1)},
        "command": f'FT.SEARCH demo:vs_idx "*=>[KNN {req.k} @embedding $v]" PARAMS 2 v [query_vector] DIALECT 2',
    }

# --- Semantic Cache ---

class CacheQuery(BaseModel):
    prompt: str
    threshold: float = 0.15

@app.post("/api/semantic-cache/setup")
def sc_setup():
    try: vk.execute_command("FT.DROPINDEX", "demo:cache_idx")
    except: pass
    for k in vk.keys("demo:cache:*"): vk.delete(k)
    vk.execute_command(
        "FT.CREATE", "demo:cache_idx", "ON", "HASH", "PREFIX", "1", "demo:cache:",
        "SCHEMA", "prompt", "TAG", "response", "TAG",
        "embedding", "VECTOR", "HNSW", "6", "TYPE", "FLOAT32", "DIM", "1536", "DISTANCE_METRIC", "COSINE",
    )
    return {"status": "ok"}

@app.post("/api/semantic-cache/ask")
def sc_ask(req: CacheQuery):
    t0 = time.perf_counter()
    query_emb = embed(req.prompt)
    embed_ms = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()
    results = vk.execute_command(
        "FT.SEARCH", "demo:cache_idx", "*=>[KNN 1 @embedding $v]",
        "PARAMS", "2", "v", vec(query_emb), "DIALECT", "2",
    )
    search_ms = (time.perf_counter() - t1) * 1000
    commands = [f'# Embed: "{req.prompt[:50]}" -> [1536-dim vector]',
                'FT.SEARCH demo:cache_idx "*=>[KNN 1 @embedding $v]" PARAMS 2 v [query_vector] DIALECT 2']

    if results[0] > 0:
        docs = parse_results(results)
        score = float(docs[0].get("__embedding_score", 999))
        if score < req.threshold:
            total_ms = (time.perf_counter() - t0) * 1000
            commands.append(f"# CACHE HIT - cosine distance {score:.4f} < threshold {req.threshold}")
            return {"hit": True, "response": docs[0].get("response", ""), "cached_prompt": docs[0].get("prompt", ""),
                    "score": round(score, 4),
                    "latency": {"embed_ms": round(embed_ms, 1), "search_ms": round(search_ms, 2), "llm_ms": 0, "total_ms": round(total_ms, 1)},
                    "commands": commands}

    t2 = time.perf_counter()
    answer = llm(req.prompt)
    llm_ms = (time.perf_counter() - t2) * 1000
    cache_key = f"demo:cache:{hashlib.md5(req.prompt.encode()).hexdigest()[:12]}"
    vk.hset(cache_key, mapping={"prompt": req.prompt, "response": answer, "embedding": vec(query_emb)})
    vk.expire(cache_key, 3600)
    total_ms = (time.perf_counter() - t0) * 1000
    nearest_score = float(parse_results(results)[0].get("__embedding_score", 999)) if results[0] > 0 else None
    commands += [f"# CACHE MISS - calling Claude Haiku ({llm_ms:.0f}ms)...",
                 f'HSET {cache_key} prompt "..." response "..." embedding [1536-dim vector]',
                 f"EXPIRE {cache_key} 3600"]
    return {"hit": False, "response": answer, "score": round(nearest_score, 4) if nearest_score else None,
            "latency": {"embed_ms": round(embed_ms, 1), "search_ms": round(search_ms, 2), "llm_ms": round(llm_ms, 1), "total_ms": round(total_ms, 1)},
            "commands": commands}

# --- Rate Limiting ---

class RateLimitReq(BaseModel):
    user_id: str = "demo-user"
    max_requests: int = 10
    window: int = 60

@app.post("/api/rate-limit/check")
def rl_check(req: RateLimitReq):
    t0 = time.perf_counter()
    window_num = int(time.time() // req.window)
    key = f"demo:rl:{req.user_id}:{window_num}"
    pipe = vk.pipeline(transaction=True)
    pipe.incr(key)
    pipe.expire(key, req.window)
    pipe.ttl(key)
    r = pipe.execute()
    ms = (time.perf_counter() - t0) * 1000
    return {"allowed": r[0] <= req.max_requests, "current": r[0], "limit": req.max_requests,
            "remaining": max(0, req.max_requests - r[0]), "ttl": r[2], "latency_ms": round(ms, 2),
            "commands": [f"INCR {key}", f"EXPIRE {key} {req.window}", f"TTL {key}"]}

@app.post("/api/rate-limit/reset")
def rl_reset():
    for k in vk.keys("demo:rl:*"): vk.delete(k)
    return {"status": "ok"}
