# AutoResearcher 🔬

**Autonomous Multi-Agent System for Scientific Literature Analysis**

> Built with LangGraph · LangChain · FastAPI · ChromaDB · Ollama · Langfuse · MinIO — fully open-source and self-hostable.

AutoResearcher is a cyclic multi-agent system for automated scientific literature research. It decomposes a research query into sub-questions, retrieves relevant papers, performs semantic ranking and deduplication, evaluates topic coverage, iterates on gaps, and synthesizes a structured Markdown literature review.

---

## Current Status

The project is working through **Step 7**.

- [x] Step 1 — Project setup, Docker Compose, Langfuse self-hosted
- [x] Step 2 — ChromaDB RAG backend with sentence-transformers embeddings
- [x] Step 3 — LangGraph StateGraph with cyclic gap-check routing
- [x] Step 4 — Agent implementations (Planner, Retriever, Critic, Synthesizer)
- [x] Step 5 — FastAPI REST layer with Langfuse tracing injection
- [x] Step 6 — Evaluation suite with Langfuse datasets
- [x] Step 7 — Dockerfile for FastAPI app and full one-command deploy
- [ ] Step 8 — Semantic Scholar / PubMed as additional paper sources

This means the stack now supports Docker-based infrastructure, local LLM inference via Ollama, a FastAPI research API, ChromaDB-based retrieval, Langfuse tracing, and dataset-driven evaluation.

---

## What the System Does

A user submits a research topic to the API. The system then:

1. Breaks the topic into sub-questions.
2. Retrieves papers from scientific sources.
3. Stores and searches papers semantically in ChromaDB.
4. Critiques the quality and coverage of current results.
5. Repeats retrieval if major gaps remain.
6. Produces a final literature-analysis report.

---

## Architecture Overview

```text
User (POST /research)
        │
        ▼
FastAPI (HTTP/JSON API)
        │
        ▼
LangGraph StateGraph (LangChain-based agents)
        │
        ├─ Planner     (LLM via Ollama)
        ├─ Retriever   (paper search + embeddings + ChromaDB)
        ├─ Critic      (coverage scoring + gap analysis)
        └─ Synthesizer (final Markdown report)
        │
        ▼
ChromaDB (vector store)
        │
        ▼
JSON response (report + sources + metrics)
        │
        ▼
Langfuse (traces, spans, eval scores)
```

---

## Tech Stack and What Each Part Does

| Component | Role in AutoResearcher |
|---|---|
| **FastAPI** | Exposes `/health` and `/research`, validates request payloads, returns JSON responses, and provides Swagger UI at `/docs`. |
| **LangChain** | Handles prompt templates, model wrappers, and retrieval abstractions used by the agents. |
| **LangGraph** | Orchestrates the cyclic Planner → Retriever → Critic → Synthesizer workflow using shared state. |
| **Ollama** | Runs the LLM locally (for example `llama3.2`) and powers planning, critique, and synthesis. |
| **ChromaDB** | Stores embedded paper representations and performs semantic similarity search for RAG. |
| **sentence-transformers** | Creates embeddings for paper titles/abstracts and sub-queries before retrieval. |
| **Langfuse** | Captures traces, spans, LLM events, and evaluation scores; also stores evaluation datasets and runs. |
| **MinIO** | Provides S3-compatible event/object storage for Langfuse. |
| **Postgres** | Stores Langfuse metadata and configuration data. |
| **ClickHouse** | Stores analytical data and evaluation metrics for Langfuse. |
| **Redis** | Acts as the queue/cache layer for Langfuse workers. |
| **Docker Compose** | Starts the full infrastructure stack and now also supports the FastAPI deployment workflow. |

---

## Multi-Agent Workflow

### Planner

The Planner agent receives the original research query and turns it into focused sub-questions. This improves retrieval quality because the system does not search using only one broad prompt.

### Retriever

The Retriever agent queries paper sources, embeds titles and abstracts, stores them in ChromaDB, performs semantic search, ranks the results, and removes duplicates.

### Critic

The Critic agent inspects the current set of retrieved papers and estimates whether the topic coverage is sufficient. It returns a `coverage_score` and textual notes describing missing areas or weak coverage.

### Synthesizer

The Synthesizer agent converts the retrieved evidence into a final Markdown literature-analysis report with sections such as overview, methods, comparisons, limitations, and open research directions.

---

## Repository Structure

```text
autoresearcher/
├── Dockerfile
├── docker-compose.yml
├── .env
├── .env.example
├── requirements.txt
├── start.ps1
├── scripts/
│   ├── create_eval_dataset.py
│   └── run_eval_on_dataset.py
├── app/
│   ├── main.py
│   ├── agents/
│   │   ├── planner.py
│   │   ├── retriever.py
│   │   ├── critic.py
│   │   └── synthesizer.py
│   ├── graph/
│   │   ├── state.py
│   │   └── workflow.py
│   ├── rag/
│   │   ├── arxiv_fetcher.py
│   │   └── chroma_store.py
│   └── observability/
│       └── langfuse_client.py
└── chroma_db/
```

---

## Infrastructure Stack

The project uses a self-hosted observability and evaluation stack:

- **Langfuse Web** — available at `http://localhost:3000`
- **Langfuse Worker** — background processing for traces/events
- **Postgres** — metadata database
- **ClickHouse** — analytics database
- **Redis** — queue/cache service
- **MinIO** — object storage, console at `http://localhost:9001`

The current environment also includes:

- `LANGFUSE_BASE_URL=http://localhost:3000`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3.2`
- `CHROMA_PERSIST_DIR=./chroma_db`
- `CHROMA_COLLECTION=autoresearcher_papers`
- `EMBED_MODEL=all-MiniLM-L6-v2`
- `CRITIC_THRESHOLD=0.75`
- `MAX_CYCLES=3`

---

## FastAPI Endpoints

### `GET /health`

Used to verify the system is up and dependencies are reachable. A healthy response confirms the FastAPI app is running and can access the configured components.

### `POST /research`

Accepts a JSON body like:

```json
{
  "query": "transformer architectures for video understanding",
  "max_papers": 12,
  "max_cycles": 2
}
```

Returns a JSON response containing:

- `report` — final Markdown literature report
- `sources` — retrieved and selected paper metadata
- `coverage_score` — Critic score for current run
- `cycles_completed` — number of executed graph cycles

### `GET /docs`

FastAPI automatically exposes Swagger UI at:

```text
http://localhost:8000/docs
```

This is the easiest way to manually test `POST /research`.

---

## How to Run the Project

### Option 1 — Full local launcher

```powershell
.\start.ps1
```

This command:

- checks Python, Docker, and Ollama,
- loads environment variables,
- creates or reuses `.venv`,
- installs dependencies,
- starts Docker services,
- starts FastAPI,
- runs the evaluation suite.

### Option 2 — Start stack without evaluation

```powershell
.\start.ps1 -NoEval
```

Use this when you want to run your own research queries manually without launching the benchmark evaluation pipeline.

### Option 3 — Stop everything

```powershell
.\start.ps1 -Stop
```

---

## How to Run a Single Research Query

After the stack is running:

1. Open your browser.
2. Visit `http://localhost:8000/docs`.
3. Expand `POST /research`.
4. Click **Try it out**.
5. Paste a JSON body such as:

```json
{
  "query": "transformer architectures for video understanding",
  "max_papers": 12,
  "max_cycles": 2
}
```

6. Click **Execute**.
7. Read the `report` field in the JSON response.

This is where you see the final literature-analysis output for your own topic.

---

## How to Use Langfuse

Open:

```text
http://localhost:3000
```

Langfuse is used for:

- viewing traces for individual `/research` runs,
- inspecting Planner / Retriever / Critic / Synthesizer spans,
- comparing evaluation runs,
- analyzing scores such as coverage and keyword relevance,
- managing datasets for reproducible evaluation.

Important: Langfuse is mainly for observability and evaluation, not for reading the final report as an end-user. The report itself is returned by the FastAPI `/research` endpoint.

---

## Evaluation Suite

The evaluation system is already integrated.

### Files

- `scripts/create_eval_dataset.py`
- `scripts/run_eval_on_dataset.py`

### What it does

- Creates a Langfuse dataset of benchmark research questions.
- Runs the full AutoResearcher pipeline on each dataset item.
- Stores traces and scores in Langfuse.
- Lets you compare experiments across models or settings.

### Typical metrics

- `coverage_score`
- keyword relevance
- per-trace outputs
- run-level comparisons in Langfuse datasets UI

---

## Step 7 Completion Criteria

Step 7 is considered complete when all of the following work:

- Docker infrastructure stack starts successfully.
- FastAPI application is reachable.
- `http://localhost:8000/health` responds successfully.
- `http://localhost:8000/docs` opens Swagger UI.
- `POST /research` returns a valid report.
- Langfuse traces appear in `http://localhost:3000`.

---

## Next Step

### Step 8 — Additional paper sources

Planned next work:

- Semantic Scholar integration
- PubMed integration
- unified paper schema across multiple sources
- better source-aware deduplication
- broader coverage beyond arXiv-only retrieval

---

## License

MIT
