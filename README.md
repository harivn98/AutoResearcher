# AutoResearcher

**Autonomous Multi-Agent System for Literature Analysis**

An end-to-end open-source pipeline that performs automated scientific literature research using a cyclic multi-agent architecture. Built with LangGraph, ChromaDB, FastAPI, Ollama, and Langfuse — fully self-hostable, zero proprietary dependencies.

---

## Architecture Overview

```
User Request (FastAPI)
        │
        ▼
 ┌─────────────────────────────────────────────────┐
 │              LangGraph StateGraph               │
 │                                                 │
 │  ┌──────────┐    ┌───────────┐    ┌──────────┐  │
 │  │ Planner  │───▶│ Retriever │───▶│  Critic  │  │
 │  └──────────┘    └───────────┘    └──────────┘  │
 │        ▲                               │        │
 │        │         Gap found?            │        │
 │        └──────── re-plan ◀─────────────┤        │
 │                                        │        │
 │                               No gap?  │        │
 │                                        ▼        │
 │                            ┌───────────────────┐│
 │                            │    Synthesizer    ││
 │                            └───────────────────┘│
 └─────────────────────────────────────────────────┘
        │
        ▼
 Structured Report (JSON/Markdown)
        │
        ▼
 Langfuse Traces (http://localhost:3000)
```

---

## Tech Stack

| Component | Tool | License |
|-----------|------|---------|
| Agent orchestration | LangGraph | MIT |
| Vector store / RAG | ChromaDB | Apache 2.0 |
| Local LLM inference | Ollama (Llama 3.2) | MIT |
| Embeddings | sentence-transformers | Apache 2.0 |
| REST API | FastAPI | MIT |
| Observability & tracing | Langfuse (self-hosted) | MIT |
| Paper source | arXiv public API | Free |

---

## Project Structure

```
autoresearcher/
├── docker-compose.yml          # Langfuse + Postgres + Clickhouse + Redis
├── .env                        # Secrets and config (never commit)
├── .env.example                # Template for .env
├── requirements.txt
├── app/
│   ├── main.py                 # FastAPI entrypoint
│   ├── agents/
│   │   ├── planner.py          # Decomposes query into sub-questions
│   │   ├── retriever.py        # arXiv fetch + ChromaDB semantic search
│   │   ├── critic.py           # Gap analysis + quality scoring
│   │   └── synthesizer.py      # Final report generation
│   ├── graph/
│   │   └── workflow.py         # LangGraph StateGraph definition
│   ├── rag/
│   │   └── chroma_store.py     # ChromaDB collection + embedding logic
│   └── observability/
│       └── langfuse_client.py  # Langfuse callback handler
├── chroma_db/                  # Persisted ChromaDB data (auto-created)
└── README.md
```

---

## Quickstart

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- [Ollama](https://ollama.com) installed locally

### 1. Clone and configure

```bash
git clone https://github.com/your-username/autoresearcher.git
cd autoresearcher
cp .env.example .env
```

Generate secrets for `.env`:

```bash
# Generate NEXTAUTH_SECRET and SALT
openssl rand -hex 32   # paste as NEXTAUTH_SECRET
openssl rand -hex 32   # paste as SALT

# ENCRYPTION_KEY must be exactly 64 hex characters
echo "0000000000000000000000000000000000000000000000000000000000000000"
```

### 2. Start Langfuse (self-hosted observability)

```bash
docker compose up -d
```

Wait ~2 minutes, then open [http://localhost:3000](http://localhost:3000).

1. Create an account and a new **Project**
2. Go to **Settings → API Keys → Create new key**
3. Copy `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` into your `.env`

### 3. Pull local LLM via Ollama

```bash
ollama pull llama3.2
# or for better reasoning quality:
ollama pull qwen2.5:14b
```

### 4. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Start the FastAPI server

```bash
uvicorn app.main:app --reload --port 8000
```

API is live at [http://localhost:8000](http://localhost:8000)  
Interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Usage

### POST `/research`

Triggers the full multi-agent research pipeline.

**Request:**
```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer architectures for video understanding", "max_papers": 20, "max_cycles": 3}'
```

**Response:**
```json
{
  "query": "transformer architectures for video understanding",
  "report": "## Summary\n...",
  "sources": [...],
  "cycles_completed": 2,
  "trace_url": "http://localhost:3000/trace/abc123"
}
```

### GET `/health`

```bash
curl http://localhost:8000/health
# {"status": "ok", "chroma": "connected", "ollama": "connected", "langfuse": "connected"}
```

---

## Agent Details

### Planner
Receives the user query and decomposes it into 3–5 focused sub-questions. Uses chain-of-thought prompting to identify the core research dimensions (methods, datasets, benchmarks, limitations).

### Retriever
For each sub-question:
1. Searches **arXiv** via the public REST API (no key required)
2. Embeds results with `sentence-transformers/all-MiniLM-L6-v2`
3. Stores in **ChromaDB** with metadata (title, authors, abstract, year)
4. Runs semantic similarity search to rank and deduplicate results

### Critic
Evaluates the retrieved results against the original query:
- Assigns a **coverage score** (0.0–1.0)
- Identifies **knowledge gaps** as follow-up sub-questions
- If score < threshold (default: `0.75`), routes back to Planner for another cycle

### Synthesizer
Generates the final structured report once the Critic approves:
- Markdown-formatted with sections (Background, Key Methods, Findings, Gaps)
- Includes citations to source papers
- Outputs structured JSON with `report`, `sources`, and `trace_url`

---

## Observability with Langfuse

Every agent invocation is automatically traced via the `CallbackHandler` injected into LangGraph's `.invoke()` config. In the Langfuse UI you can inspect:

- **Traces** — full execution path per research request
- **Spans** — individual agent node timings (Planner, Retriever, Critic, Synthesizer)
- **LLM calls** — prompt/completion pairs with token counts and latency
- **Scores** — the Critic's coverage score is logged as a numeric evaluation

```python
# Tracing is injected at invocation time — no code changes to agents needed
result = graph.invoke(
    {"query": query},
    config={"callbacks": [get_langfuse_handler()]}
)
```

---

## Configuration Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_MODEL` | Local LLM model name | `llama3.2` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./chroma_db` |
| `CHROMA_COLLECTION` | Collection name | `autoresearcher_papers` |
| `LANGFUSE_HOST` | Langfuse server URL | `http://localhost:3000` |
| `LANGFUSE_PUBLIC_KEY` | From Langfuse UI | — |
| `LANGFUSE_SECRET_KEY` | From Langfuse UI | — |
| `MAX_CYCLES` | Max critic-replan loops | `3` |
| `CRITIC_THRESHOLD` | Min coverage score to accept | `0.75` |

---

## Development Roadmap

- [x] Step 1 — Project setup, Docker Compose, Langfuse self-hosted
- [ ] Step 2 — ChromaDB RAG backend with sentence-transformers embeddings
- [ ] Step 3 — LangGraph StateGraph with cyclic gap-check routing
- [ ] Step 4 — Individual agent implementations (Planner, Retriever, Critic, Synthesizer)
- [ ] Step 5 — FastAPI REST layer with Langfuse tracing injection
- [ ] Step 6 — Evaluation suite with Langfuse datasets
- [ ] Step 7 — Docker-compose service for the FastAPI app (full one-command deploy)

---

## License

MIT — see [LICENSE](LICENSE)

---

## Acknowledgements

Built with [LangGraph](https://github.com/langchain-ai/langgraph), [ChromaDB](https://www.trychroma.com), [Langfuse](https://langfuse.com), [Ollama](https://ollama.com), and [FastAPI](https://fastapi.tiangolo.com).
