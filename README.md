# Valkey for AI

A practical, use-case-driven hub that helps developers understand how to use Valkey in real AI workloads. Instead of making users piece together low-level features, this site offers clear cookbooks, reference architectures, GitHub demos, and runnable projects for patterns like semantic caching, conversation memory, vector search, agent session state, rate limiting, streaming responses, and more.

🌐 **Live Site**: [valkeyforai.com](https://main.d35f7zfvosyphf.amplifyapp.com/) (or GitHub Pages URL)

## 🎯 Goal

Help builders quickly go from "I'm trying to solve this AI problem" to "here's exactly how Valkey fits, why it works, and how to implement it in production."

## ✨ Features

### 🏠 Modern UI/UX
- **Apple-inspired Design**: Clean, minimalist interface with Inter font and glassmorphism effects
- **Responsive Layout**: Works perfectly on desktop, tablet, and mobile
- **Smooth Animations**: Subtle scroll-triggered animations and micro-interactions

### 📚 Comprehensive Cookbooks

**Feature Store Cookbooks** (6 guides):
1. **Getting Started** - Setup and basic feature operations
2. **Online Serving** - Sub-millisecond feature lookups with batch pipelines  
3. **Real-Time Aggregations** - Sliding windows, rolling averages, HyperLogLog
4. **Streaming Updates** - Real-time pipelines with Valkey Streams
5. **ML Integration** - Direct integration with scikit-learn, FastAPI, LLMs
6. **Production Patterns** - Monitoring, versioning, health checks

**Rate Limiting Cookbooks** (6 guides):
1. **Getting Started** - Fixed-window rate limiting basics
2. **Token-Aware Limiting** - LLM token consumption tracking
3. **Agent Rate Limiting** - Multi-agent conversation management
4. **Hierarchical Limits** - User/organization/global limit tiers
5. **Cost-Based Limiting** - Usage cost tracking and limits
6. **Production Patterns** - Distributed limiting, monitoring

### 🎮 Interactive Demos
- **Feature Store Demo** - Create entities, write features, measure latency
- **Rate Limiter Demo** - Test different limiting algorithms in real-time

### 🏗️ Architecture Examples
- Real-time ML feature serving
- AI agent session management
- Semantic caching for LLMs
- Vector search pipelines

## 🚀 Quick Start

### Local Development
```bash
# Clone the repository
git clone https://github.com/[username]/valkeyforai.git
cd valkeyforai

# Serve locally (any static server works)
python -m http.server 8000
# or
npx serve .
# or
open index.html
```

### Project Structure
```
valkeyforai/
├── index.html              # Landing page
├── styles.css              # Main stylesheet
├── script.js               # Interactive functionality
├── valkey-logo.svg          # Valkey logo
├── cookbooks/
│   ├── cookbook.css         # Cookbook styling
│   ├── feature-store/       # 6 feature store guides
│   │   ├── index.html
│   │   ├── 01-getting-started.html
│   │   ├── 02-online-serving.html
│   │   ├── 03-realtime-aggregations.html
│   │   ├── 04-streaming-updates.html
│   │   ├── 05-ml-integration.html
│   │   └── 06-production.html
│   └── rate-limiting/       # 6 rate limiting guides
│       ├── index.html
│       └── [01-06].html
└── demo/
    ├── feature-store.html   # Interactive feature store
    └── rate-limiter.html    # Interactive rate limiter
```

## 🛠️ Technology Stack

- **Frontend**: Pure HTML, CSS, JavaScript (no build tools needed)
- **Styling**: Custom CSS with Apple design principles
- **Icons**: Lucide icons via CDN
- **Fonts**: Inter from Google Fonts
- **Hosting**: GitHub Pages ready

## 🎨 Design Philosophy

Following Apple's design principles:
- **Clarity** - Clean typography and generous whitespace
- **Deference** - Content is king, UI stays out of the way  
- **Depth** - Subtle layering with glassmorphism and shadows
- **Performance** - Optimized for fast loading and smooth interactions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test locally to ensure everything works
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Content Guidelines
- Keep cookbooks practical and production-focused
- Include real code examples that actually work
- Test all Valkey commands and code snippets
- Follow the existing Apple-inspired design patterns

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- [Valkey](https://github.com/valkey-io/valkey) - The official Valkey repository
- [Valkey Documentation](https://valkey.io/docs/) - Official Valkey docs

## 💡 Acknowledgments

- Valkey community for the amazing in-memory database
- Apple for design inspiration
- All contributors who help make AI + Valkey more accessible

---

**Built with ❤️ for the AI community**
