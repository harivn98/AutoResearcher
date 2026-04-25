# AutoResearcher 🔬

**Autonomous Multi-Agent System for Scientific Literature Analysis**

> Built with LangGraph · ChromaDB · FastAPI · Ollama · Langfuse — 100% open-source, fully self-hostable, zero proprietary dependencies.

AutoResearcher is a cyclic multi-agent pipeline that performs automated scientific literature research. Given a research topic, it autonomously decomposes the query, fetches papers from arXiv, ranks and deduplicates results using semantic search, self-evaluates coverage quality, iteratively fills knowledge gaps, and synthesizes a structured Markdown literature review.

---

## Demo Output

**Query:** `"transformer architectures for video understanding"`

```json
{
  "cycles_completed": 2,
  "coverage_score": 0.75,
  "report": "## Overview\nTransformer architectures have been increasingly applied...",
  "sources": [
    { "title": "InternVideo2: Scaling Foundation Models for Multimodal Video Understanding", "year": "2024" },
    { "title": "Video Understanding: From Geometry and Semantics to Unified Models", "year": "2026" },
    { "title": "ModelScope Text-to-Video Technical Report", "year": "2023" }
  ]
}
```

---

## Architecture

```
User Request (POST /research)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                LangGraph StateGraph                 │
│                                                     │
│  ┌──────────┐   ┌───────────┐   ┌───────────────┐  │
│  │ Planner  │──▶│ Retriever │──▶│    Critic     │  │
│  └──────────┘   └───────────┘   └───────────────┘  │
│       ▲                                  │          │
│       │         gap found?               │          │
│       └──────── re-plan ◀────────────────┤          │
│                                          │          │
│                               approved?  │          │
│                                          ▼          │
│                           ┌─────────────────────┐   │
│                           │    Synthesizer      │   │
│                           └─────────────────────┘   │
└─────────────────────────────────────────────────────┘
        │
        ▼
Structured Report (JSON + Markdown)
        │
        ▼
Langfuse Traces (http://localhost:3000)
```

### Agent Roles

| Agent | Responsibility |
|---|---|
| **Planner** | Decomposes the user query into 3–5 focused literature search sub-questions using chain-of-thought |
| **Retriever** | Fetches papers from arXiv API, embeds with `sentence-transformers`, stores in ChromaDB, ranks by semantic similarity, deduplicates |
| **Critic** | Scores coverage (0.0–1.0), identifies knowledge gaps, decides approve vs re-plan |
| **Synthesizer** | Generates structured Markdown literature review (Overview, Key Methods, Findings, Gaps, Sources) |

---

## Tech Stack

| Component | Tool | License |
|---|---|---|
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) | MIT |
| LLM framework | [LangChain](https://github.com/langchain-ai/langchain) | MIT |
| Local LLM inference | [Ollama](https://ollama.com) | MIT |
| Vector store / RAG | [ChromaDB](https://www.trychroma.com) | Apache 2.0 |
| Embeddings | [sentence-transformers](https://www.sbert.net) | Apache 2.0 |
| REST API | [FastAPI](https://fastapi.tiangolo.com) | MIT |
| Observability & tracing | [Langfuse](https://langfuse.com) (self-hosted) | MIT |
| Paper source | [arXiv public API](https://arxiv.org/help/api) | Free |

---

## Project Structure

```
autoresearcher/
├── docker-compose.yml              # Langfuse + Postgres + Clickhouse + Redis
├── .env                            # Secrets and config (never commit)
├── .env.example                    # Template for .env
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entrypoint (/health, /research)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py              # Query decomposition → sub-questions
│   │   ├── retriever.py            # arXiv fetch + ChromaDB ingest + semantic search
│   │   ├── critic.py               # Gap analysis + coverage scoring
│   │   └── synthesizer.py         # Final Markdown report generation
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py                # ResearchState TypedDict
│   │   ├── workflow.py             # LangGraph StateGraph + run_research()
│   │   └── graph_viz.py           # Mermaid diagram export utility
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── chroma_store.py        # ChromaDB CRUD + deduplication
│   │   └── arxiv_fetcher.py       # arXiv Atom API client
│   └── observability/
│       ├── __init__.py
│       └── langfuse_client.py     # Langfuse callback handler setup
├── chroma_db/                      # Persisted ChromaDB data (auto-created)
└── README.md
```

---

## Quickstart

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running
- Docker Desktop (for Langfuse observability — optional)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/autoresearcher.git
cd autoresearcher
cp .env.example .env
```

### 2. Create and activate virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

> **Windows note:** If you get a script execution error, run once as Admin:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Pull local LLM

```bash
# Fast and reliable (recommended for 16 GB RAM)
ollama pull llama3.2

# Better reasoning quality (RTX 4070 / 16 GB+ RAM)
ollama pull qwen2.5:14b
```

Set `OLLAMA_MODEL` in `.env` to match your chosen model.

### 5. Create `__init__.py` files (Windows only)

```powershell
ni app\__init__.py -Force
ni app\agents\__init__.py -Force
ni app\graph\__init__.py -Force
ni app\rag\__init__.py -Force
ni app\observability\__init__.py -Force
```

### 6. Start the API server

```bash
uvicorn app.main:app --reload --port 8000
```

API is live at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

---

## API Reference

### `GET /health`

Returns the status of all connected services.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "chroma": "connected",
  "ollama": "connected",
  "langfuse": "configured",
  "model": "llama3.2",
  "total_papers": 23
}
```

---

### `POST /research`

Runs the full multi-agent research pipeline.

**Request:**
```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer architectures for video understanding", "max_papers": 12, "max_cycles": 2}'
```

**Parameters:**

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | string | required | Research topic or question |
| `max_papers` | int | 20 | Max papers fetched per cycle (5–100) |
| `max_cycles` | int | 3 | Max Critic→Planner re-planning loops (1–6) |

**Response:**

```json
{
  "query": "transformer architectures for video understanding",
  "report": "## Overview\n...",
  "sources": [
    {
      "title": "InternVideo2: Scaling Foundation Models...",
      "authors": "Yi Wang et al.",
      "year": "2024",
      "arxiv_id": "2403.15377v4",
      "url": "https://arxiv.org/pdf/2403.15377v4",
      "similarity_score": 0.4869
    }
  ],
  "cycles_completed": 2,
  "coverage_score": 0.75,
  "critic_feedback": "Good coverage of recent transformer approaches...",
  "langfuse_enabled": true,
  "trace_hint": "Open http://localhost:3000 and inspect the latest trace"
}
```

---

## Observability with Langfuse (Optional)

Langfuse provides full end-to-end tracing for every agent call, LLM prompt/completion pair, and token usage.

### Start Langfuse (self-hosted)

```bash
docker compose up -d
```

Then open `http://localhost:3000`:

1. Create an account and a **Project**
2. Go to **Settings → API Keys → Create new key**
3. Copy both keys into `.env`:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

4. Restart the API server

You'll see every agent call traced in the Langfuse dashboard with:
- Full execution path per research request
- Individual agent node timings
- LLM prompt/completion pairs with token counts
- Critic coverage scores logged as numeric evaluations

### Disable Langfuse

Leave the keys empty in `.env` and the system runs without any observability warnings:

```env
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

---

## Configuration Reference

| Variable | Description | Default |
|---|---|---|
| `OLLAMA_MODEL` | Local LLM model name | `llama3.2` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./chroma_db` |
| `CHROMA_COLLECTION` | Vector store collection name | `autoresearcher_papers` |
| `EMBED_MODEL` | sentence-transformers model | `all-MiniLM-L6-v2` |
| `CRITIC_THRESHOLD` | Min coverage score to approve (0.0–1.0) | `0.75` |
| `MAX_CYCLES` | Max re-planning loops | `3` |
| `LANGFUSE_HOST` | Langfuse server URL | `http://localhost:3000` |
| `LANGFUSE_PUBLIC_KEY` | From Langfuse UI | — |
| `LANGFUSE_SECRET_KEY` | From Langfuse UI | — |

---

## `.env.example`

```env
# Langfuse (generate with: openssl rand -hex 32)
NEXTAUTH_SECRET=your_nextauth_secret_here
SALT=your_salt_here
ENCRYPTION_KEY=0000000000000000000000000000000000000000000000000000000000000000

# Langfuse API keys (fill after first docker compose up → http://localhost:3000)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=http://localhost:3000

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# ChromaDB
CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION=autoresearcher_papers
EMBED_MODEL=all-MiniLM-L6-v2

# Agent tuning
CRITIC_THRESHOLD=0.75
MAX_CYCLES=3
```

---

## Recommended Models by Hardware

| VRAM / RAM | Recommended Model | Quality |
|---|---|---|
| 8 GB RAM | `llama3.2:3b` | Basic |
| 16 GB RAM | `llama3.2` (8B) | Good |
| 16 GB RAM + RTX 4070 8GB | `qwen2.5:14b` | Better reasoning |
| 32 GB RAM | `qwen2.5:32b` | Best |

---

## How the Cyclic Loop Works

```
1. Planner   → decomposes query into sub-questions
2. Retriever → fetches arXiv papers, embeds, stores in ChromaDB, deduplicates
3. Critic    → scores coverage 0.0–1.0
               if score ≥ threshold → Synthesizer
               if score < threshold AND cycles remaining → back to Planner
               if max cycles reached → force Synthesizer
4. Synthesizer → generates final Markdown report
```

The `papers` field in `ResearchState` uses `operator.add` — papers **accumulate** across cycles
rather than being overwritten, so each re-plan adds new evidence on top of existing results.

---

## Development Roadmap

- [x] Step 1 — Project setup, Docker Compose, Langfuse self-hosted
- [x] Step 2 — ChromaDB RAG backend with sentence-transformers embeddings
- [x] Step 3 — LangGraph StateGraph with cyclic gap-check routing
- [x] Step 4 — Agent implementations (Planner, Retriever, Critic, Synthesizer)
- [x] Step 5 — FastAPI REST layer with Langfuse tracing injection
- [x] Working — Full end-to-end pipeline confirmed
- [ ] Step 6 — Evaluation suite with Langfuse datasets
- [ ] Step 7 — Dockerfile for the FastAPI app (full one-command deploy)
- [ ] Step 8 — Semantic Scholar / PubMed as additional paper sources

---

## License

MIT — see [LICENSE](LICENSE)

---

## Acknowledgements

Built with [LangGraph](https://github.com/langchain-ai/langgraph) · [ChromaDB](https://www.trychroma.com) · [Langfuse](https://langfuse.com) · [Ollama](https://ollama.com) · [FastAPI](https://fastapi.tiangolo.com) · [sentence-transformers](https://www.sbert.net) · [arXiv API](https://arxiv.org/help/api)
