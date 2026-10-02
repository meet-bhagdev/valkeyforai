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

## Prefer Jupyter Notebooks?

Every cookbook is also available as a generated `.ipynb` file for readers who
prefer to run examples interactively in JupyterLab or VS Code.

```bash
uv sync
uv run jupyter lab notebooks/
```

See [Jupyter Notebooks](docs/Jupyter_Notebooks.md) for why the project provides
notebooks, how Markdown cookbooks are converted, and how contributors keep the
generated files current. Save personal experiments outside `notebooks/`
because files in that directory are regenerated from Markdown.

## Contributing

### Editing cookbooks

All cookbook content lives in markdown files under `content/`. Each cookbook is built into HTML under `cookbooks/` and a Jupyter notebook under `notebooks/`. When you push to `main`, a GitHub Action regenerates both formats and the site updates automatically.

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
3. Run `npm run build` locally to regenerate the HTML and notebook
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
| `build-notebooks.js` | Markdown-to-notebook builder | Generates and validates `notebooks/<track>/*.ipynb` |

### Running the build locally

```bash
npm install        # first time only
npm run build      # builds HTML and notebooks for all tracks
npm run build:html -- semantic-caching
npm run build:notebooks -- semantic-caching
```

### Generating and checking Jupyter notebooks

Every cookbook has a tracked `.ipynb` notebook for use in JupyterLab, Colab, or VS Code. Cookbook pages link directly to their notebook.

The complete generation and contribution workflow is documented in
[Jupyter Notebooks](docs/Jupyter_Notebooks.md).

```bash
npm run build:notebooks   # regenerate every notebook
npm run check:notebooks   # fail on missing, stale, or orphan notebooks
```

Notebooks are generated from the same markdown source in `content/`. Python blocks become code cells, shell commands use `%%bash` cells, environment snippets and other languages stay as fenced Markdown, and prose stays as Markdown cells.

### Testing the build workflow locally

The GitHub Action that regenerates artifacts can be reproduced locally before
you push. See [Testing the Build Workflow Locally](docs/Local_CI_Testing.md)
for the full workflow breakdown and three ways to test it. The quickest
pre-flight check:

```bash
npm ci && npm run build && npm run check:notebooks \
  && git status --porcelain -- cookbooks/ notebooks/
```

A clean run with no trailing output means the pull-request artifact check will pass.

## Project structure

```
valkeyforai/
├── index.html                # Homepage
├── styles.css                # Site styles
├── script.js                 # Homepage interactions
├── build.js                  # Markdown → HTML builder
├── build-notebooks.js        # Markdown → Jupyter notebook builder
├── docs/                     # Project documentation
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
├── notebooks/                # Generated Jupyter notebooks
├── demo/                     # Interactive demos
└── use-cases/                # Use-case overview pages
```

## Tech stack

- Pure HTML/CSS/JS (no framework, with small Node.js build scripts)
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
