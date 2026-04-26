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
| Object storage (traces) | [MinIO](https://min.io) (self-hosted S3) | AGPL-3.0 |
| Paper source | [arXiv public API](https://arxiv.org/help/api) | Free |

---

## Project Structure

```
autoresearcher/
├── docker-compose.yml              # Langfuse + Postgres + Clickhouse + Redis + MinIO
├── .env                            # Secrets and config (never commit)
├── .env.example                    # Template for .env
├── requirements.txt
├── scripts/
│   ├── create_eval_dataset.py      # Creates Langfuse evaluation dataset
│   └── run_eval_on_dataset.py      # Runs pipeline over dataset, logs scores
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entrypoint (/health, /research)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py
│   │   ├── retriever.py
│   │   ├── critic.py
│   │   └── synthesizer.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── workflow.py
│   │   └── graph_viz.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── chroma_store.py
│   │   └── arxiv_fetcher.py
│   └── observability/
│       ├── __init__.py
│       └── langfuse_client.py
├── chroma_db/                      # Persisted ChromaDB data (auto-created)
└── README.md
```

---

## Quickstart

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and **running** (for Langfuse)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/autoresearcher.git
cd autoresearcher
cp .env.example .env
```

### 2. Generate secrets for `.env`

```python
# Run in Python to generate values
import secrets
print(secrets.token_hex(32))   # use for NEXTAUTH_SECRET
print(secrets.token_hex(32))   # use for SALT
print(secrets.token_hex(32))   # use for ENCRYPTION_KEY
```

### 3. Create and activate virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If you get a script execution error, run once as Admin:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Create package markers (Windows)

```powershell
ni app\__init__.py -Force
ni app\agents\__init__.py -Force
ni app\graph\__init__.py -Force
ni app\rag\__init__.py -Force
ni app\observability\__init__.py -Force
ni scripts\__init__.py -Force
```

### 6. Start Langfuse (self-hosted)

Make sure **Docker Desktop is open and running**, then:

```powershell
docker compose up -d
```

This starts: `langfuse-web`, `langfuse-worker`, `postgres`, `clickhouse`, `redis`, `minio`, `minio-init`.

Wait ~2–3 minutes, then open `http://localhost:3000`.

1. Create an account and a **Project**
2. Go to **Settings → API Keys → Create new key**
3. Copy both keys into your `.env`:

```env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://localhost:3000
```

### 7. Pull local LLM

```bash
ollama pull llama3.2
# Or for better quality (RTX 4070 + 16 GB RAM):
ollama pull qwen2.5:14b
```

### 8. Start the API server

```bash
uvicorn app.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Langfuse UI: `http://localhost:3000`
- MinIO console: `http://localhost:9001` (login: `minioadmin` / `minioadmin`)

---

## API Reference

### `GET /health`

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

### `POST /research`

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

---

## Evaluation Suite with Langfuse Datasets

AutoResearcher includes an evaluation pipeline that uses Langfuse's Datasets & Experiments feature to benchmark pipeline quality across different queries and model configurations.

### How it works

```
eval_dataset.json (queries + expected keywords)
        │
        ▼
scripts/create_eval_dataset.py  →  Langfuse Dataset
        │
        ▼
scripts/run_eval_on_dataset.py  →  runs pipeline on each item
        │                          logs coverage_score + keyword_relevance
        ▼
Langfuse UI → Datasets → Runs → compare scores across experiments
```

### Step 1 — Make sure Langfuse is running

```powershell
docker compose up -d
docker ps
# Verify langfuse-web is running on port 3000
```

Open `http://localhost:3000` — it must load before running eval scripts.

### Step 2 — Create the dataset

```powershell
python scripts/create_eval_dataset.py
```

This creates a dataset named `autoresearcher-eval` in Langfuse with 10 benchmark queries across different research domains.

### Step 3 — Run the evaluation

```powershell
python scripts/run_eval_on_dataset.py
```

This runs `run_research()` on every dataset item and logs two scores per run:
- `coverage_score` — from the internal Critic agent (0.0–1.0)
- `keyword_relevance` — simple keyword match against expected terms (0.0–1.0)

### Step 4 — View results in Langfuse UI

1. Open `http://localhost:3000`
2. Go to **Datasets → autoresearcher-eval**
3. Click **Runs** tab
4. Inspect per-item scores, traces, and LLM calls

### Comparing experiments

To compare `llama3.2` vs `qwen2.5:14b`:

1. Change `OLLAMA_MODEL=qwen2.5:14b` in `.env`
2. Change `RUN_NAME` in `run_eval_on_dataset.py` to `"qwen2.5-14b-run"`
3. Run `python scripts/run_eval_on_dataset.py` again
4. In Langfuse UI → Datasets → Runs, both runs appear side by side with avg scores

---

## Observability with Langfuse

### Services started by Docker Compose

| Service | Purpose | URL |
|---|---|---|
| `langfuse-web` | Main UI + API | `http://localhost:3000` |
| `langfuse-worker` | Async trace processing | internal |
| `postgres` | Metadata storage | internal |
| `clickhouse` | Analytics / scores storage | internal |
| `redis` | Queue | internal |
| `minio` | S3-compatible trace event storage | `http://localhost:9001` |

### What gets traced

Every research request automatically traces:
- Full execution path (Planner → Retriever → Critic → Synthesizer)
- Individual agent timings
- LLM prompt/completion pairs with token counts
- Critic coverage scores as numeric evaluations

### Disable Langfuse (run without Docker)

Leave keys empty in `.env`:

```env
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

The system runs fully without tracing — `/health` will show `"langfuse": "disabled"`.

---

## Configuration Reference

| Variable | Description | Default |
|---|---|---|
| `OLLAMA_MODEL` | Local LLM model name | `llama3.2` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./chroma_db` |
| `CHROMA_COLLECTION` | Vector store collection name | `autoresearcher_papers` |
| `EMBED_MODEL` | sentence-transformers model | `all-MiniLM-L6-v2` |
| `CRITIC_THRESHOLD` | Min coverage score to approve | `0.75` |
| `MAX_CYCLES` | Max re-planning loops | `3` |
| `LANGFUSE_BASE_URL` | Langfuse server URL | `http://localhost:3000` |
| `LANGFUSE_PUBLIC_KEY` | From Langfuse UI | — |
| `LANGFUSE_SECRET_KEY` | From Langfuse UI | — |
| `NEXTAUTH_SECRET` | Auth secret (generate randomly) | — |
| `SALT` | Encryption salt (generate randomly) | — |
| `ENCRYPTION_KEY` | 32-byte hex key (generate randomly) | — |

---

## Recommended Models by Hardware

| RAM | GPU VRAM | Recommended Model | Quality |
|---|---|---|---|
| 8 GB | any | `llama3.2:3b` | Basic |
| 16 GB | — | `llama3.2` (8B) | Good |
| 16 GB | RTX 4070 8GB | `qwen2.5:14b` | Better reasoning |
| 32 GB | RTX 3090+ | `qwen2.5:32b` | Best |

---

## How the Cyclic Loop Works

```
1. Planner     → decomposes query into 3-5 sub-questions
2. Retriever   → fetches arXiv papers, embeds, stores in ChromaDB, deduplicates
3. Critic      → scores coverage 0.0–1.0
                 score ≥ threshold → Synthesizer (done)
                 score < threshold + cycles left → back to Planner with gap queries
                 max cycles reached → force Synthesizer
4. Synthesizer → generates final Markdown report
```

The `papers` field in `ResearchState` uses `operator.add` so papers **accumulate** across cycles — each re-plan adds new evidence on top of previous results.

---

## Development Roadmap

- [x] Step 1 — Project setup, Docker Compose, Langfuse self-hosted
- [x] Step 2 — ChromaDB RAG backend with sentence-transformers embeddings
- [x] Step 3 — LangGraph StateGraph with cyclic gap-check routing
- [x] Step 4 — Agent implementations (Planner, Retriever, Critic, Synthesizer)
- [x] Step 5 — FastAPI REST layer with Langfuse tracing injection
- [x] Step 6 — Evaluation suite with Langfuse datasets
- [ ] Step 7 — Dockerfile for FastAPI app (full one-command deploy)
- [ ] Step 8 — Semantic Scholar / PubMed as additional paper sources

---

## License

MIT — see [LICENSE](LICENSE)

---

## Acknowledgements

Built with [LangGraph](https://github.com/langchain-ai/langgraph) · [ChromaDB](https://www.trychroma.com) · [Langfuse](https://langfuse.com) · [Ollama](https://ollama.com) · [FastAPI](https://fastapi.tiangolo.com) · [sentence-transformers](https://www.sbert.net) · [MinIO](https://min.io) · [arXiv API](https://arxiv.org/help/api)
