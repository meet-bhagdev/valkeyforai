# Valkey for AI

Cookbooks, reference architectures, and runnable demos for using Valkey in AI workloads - semantic caching, vector search, conversation memory, agent state, rate limiting, RAG pipelines, and more.

**Live site**: [valkeyforai.com](https://main.d35f7zfvosyphf.amplifyapp.com/)

## What's here

**9 use-case tracks** with 45+ step-by-step cookbooks:

| Track | Cookbooks | What it covers |
|-------|-----------|---------------|
| Semantic Caching | 3 | Cache LLM responses by meaning, not exact match |
| Conversation Memory | 5 | Chat history, session management, semantic search |
| Vector Search | 3 | HNSW indexes, KNN queries, hybrid filters |
| RAG Pipelines | 6 | Document chunking, retrieval, caching, monitoring |
| Rate Limiting | 6 | Fixed window, token-aware, hierarchical, cost-based |
| Feature Store | 6 | Real-time feature serving for ML models |
| Pub/Sub & Streaming | 6 | LLM token streaming, consumer groups, fan-out |
| Context Engineering | 3 | Memory assembly, context budgeting, production patterns |
| Agent Session State | Coming soon | Tool call persistence, reasoning checkpoints |

**5 framework integrations:**

| Framework | Cookbooks | Integration |
|-----------|-----------|-------------|
| [Mem0](https://github.com/mem0ai/mem0) | 3 | Native `provider: "valkey"` connector |
| [LangChain / LangGraph](https://github.com/langchain-ai/langgraph) | 4 | `langgraph-checkpoint-aws` with ValkeySaver |
| [CrewAI](https://github.com/crewAIInc/crewAI) | 3 | Custom ValkeyStorage with GLIDE client |
| [Strands](https://github.com/strands-agents/sdk-python) | 3 | `strands-valkey-session-manager` package |
| [Haystack](https://github.com/deepset-ai/haystack) | 2 | `valkey-haystack` with ValkeyDocumentStore |

Each track has interactive demos on the live site.

## Quick start

```bash
git clone https://github.com/meet-bhagdev/valkeyforai.git
cd valkeyforai

# Serve locally
python -m http.server 8000
# or
npx serve .
```

Open `http://localhost:8000` in your browser.

## Contributing

### Editing cookbooks

All cookbook content lives in markdown files under `content/`. When you push to `main`, a GitHub Action runs `node build.js` to regenerate the HTML in `cookbooks/`, and the site updates automatically.

```
content/
├── semantic-caching/
│   ├── meta.json                    # Track config (titles, nav, difficulty)
│   ├── 01-getting-started.md        # ← edit this
│   ├── 02-multiturn-caching.md
│   └── 03-production.md
├── conversation-memory/
│   ├── meta.json
│   └── *.md
├── crewai/
│   ├── meta.json
│   └── *.md
└── ... (13 tracks total)
```

**To edit a cookbook:**

1. Edit the `.md` file in `content/<track>/`
2. Use fenced code blocks with language tags (` ```python `, ` ```bash `)
3. Run `node build.js` locally to preview (optional)
4. Push to `main` - the GitHub Action rebuilds and Amplify deploys

**To add a new cookbook to an existing track:**

1. Create a new `.md` file in the track's `content/` directory
2. Add an entry to `meta.json` with title, difficulty, time, and prev/next links
3. Update the prev/next links on adjacent cookbooks in `meta.json`
4. Push to `main`

**To add a new track:**

1. Create `content/<track-name>/meta.json` (copy an existing one as template)
2. Add your `.md` files
3. Create `cookbooks/<track-name>/index.html` (copy from an existing track's index)
4. Add the track to the homepage `index.html`
5. Push to `main`

### meta.json format

```json
{
  "trackName": "Semantic Caching",
  "cookbooks": [
    {
      "num": "01",
      "source": "01-getting-started.md",
      "output": "01-getting-started.html",
      "title": "Getting Started with Semantic Caching",
      "h1": "Getting Started with Semantic Caching",
      "breadcrumb": "Getting Started",
      "difficulty": "Beginner",
      "time": "15 min",
      "next": {
        "file": "02-multiturn-caching.html",
        "title": "02 - Multi-Turn Caching"
      }
    }
  ]
}
```

### Other files

| File | What it is | How to edit |
|------|-----------|-------------|
| `index.html` | Homepage | Edit directly (not generated) |
| `cookbooks/<track>/index.html` | Track landing page | Edit directly (not generated) |
| `demo/*.html` | Interactive demos | Edit directly |
| `use-cases/*/index.html` | Use-case overview pages | Edit directly |
| `styles.css` | Main site styles | Edit directly |
| `cookbooks/cookbook.css` | Cookbook page styles | Edit directly |
| `build.js` | Markdown-to-HTML builder | Generates `cookbooks/<track>/*.html` from `content/` |

### Running the build locally

```bash
npm install        # first time only
node build.js      # builds all tracks
node build.js semantic-caching   # build one track
```

## Project structure

```
valkeyforai/
├── index.html                # Homepage
├── styles.css                # Site styles
├── script.js                 # Homepage interactions
├── build.js                  # Markdown → HTML builder
├── content/                  # Markdown source (edit these)
│   ├── semantic-caching/
│   ├── conversation-memory/
│   ├── vector-search/
│   ├── rag-pipelines/
│   ├── rate-limiting/
│   ├── feature-store/
│   ├── pubsub-streaming/
│   ├── context-engineering/
│   ├── crewai/
│   ├── langchain/
│   ├── mem0/
│   ├── haystack/
│   └── strands/
├── cookbooks/                # Generated HTML (don't edit directly)
├── demo/                     # Interactive demos
└── use-cases/                # Use-case overview pages
```

## Tech stack

- Pure HTML/CSS/JS (no framework, no build tools beyond `node build.js`)
- [Inter](https://fonts.google.com/specimen/Inter) font
- [highlight.js](https://highlightjs.org/) for syntax highlighting
- Hosted on AWS Amplify

## License

MIT

## Links

- [Valkey](https://github.com/valkey-io/valkey)
- [Valkey docs](https://valkey.io/docs/)
- [valkey-py](https://github.com/valkey-io/valkey-py)
- [Valkey GLIDE](https://github.com/valkey-io/valkey-glide)
