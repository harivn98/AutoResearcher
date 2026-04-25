"""
app/main.py
FastAPI entrypoint for AutoResearcher.
Endpoints:
- GET  /health
- POST /research
- GET  /docs
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.graph.workflow import run_research
from app.rag.chroma_store import collection_stats
from app.observability.langfuse_client import init_langfuse, get_langfuse_handler, is_langfuse_enabled

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=5, description="Research topic or question")
    max_papers: int = Field(default=20, ge=5, le=100)
    max_cycles: int = Field(default=3, ge=1, le=6)


class SourceItem(BaseModel):
    title: str
    abstract: str = ""
    authors: str = ""
    year: str = ""
    arxiv_id: str = ""
    url: str = ""
    similarity_score: float = 0.0


class ResearchResponse(BaseModel):
    query: str
    report: str
    sources: List[SourceItem]
    cycles_completed: int
    coverage_score: float
    critic_feedback: str
    langfuse_enabled: bool
    trace_hint: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    chroma: str
    ollama: str
    langfuse: str
    model: str
    total_papers: int


def check_ollama() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_langfuse()
    yield


app = FastAPI(
    title="AutoResearcher API",
    version="0.1.0",
    description="Autonomous multi-agent literature analysis system using LangGraph, ChromaDB, Ollama, and Langfuse.",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    try:
        stats = collection_stats()
        chroma_status = "connected"
        total_papers = stats.get("total_papers", 0)
    except Exception:
        chroma_status = "error"
        total_papers = 0

    ollama_status = "connected" if check_ollama() else "error"
    langfuse_status = "configured" if is_langfuse_enabled() else "disabled"

    overall = "ok" if chroma_status == "connected" and ollama_status == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        chroma=chroma_status,
        ollama=ollama_status,
        langfuse=langfuse_status,
        model=OLLAMA_MODEL,
        total_papers=total_papers,
    )


@app.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest) -> ResearchResponse:
    if not check_ollama():
        raise HTTPException(status_code=503, detail="Ollama is not reachable. Start Ollama and pull the configured model first.")

    handler = get_langfuse_handler()

    try:
        state = run_research(
            query=request.query,
            max_cycles=request.max_cycles,
            max_papers=request.max_papers,
            langfuse_handler=handler,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research pipeline failed: {e}")

    sources = [SourceItem(**{
        "title": p.get("title", ""),
        "abstract": p.get("abstract", ""),
        "authors": p.get("authors", ""),
        "year": p.get("year", ""),
        "arxiv_id": p.get("arxiv_id", ""),
        "url": p.get("url", ""),
        "similarity_score": float(p.get("similarity_score", 0.0)),
    }) for p in state.get("sources", [])]

    trace_hint = f"Open {LANGFUSE_HOST} and inspect the latest trace" if is_langfuse_enabled() else None

    return ResearchResponse(
        query=state.get("query", request.query),
        report=state.get("report", ""),
        sources=sources,
        cycles_completed=state.get("cycle", 0),
        coverage_score=float(state.get("coverage_score", 0.0)),
        critic_feedback=state.get("critic_feedback", ""),
        langfuse_enabled=is_langfuse_enabled(),
        trace_hint=trace_hint,
    )


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "name": "AutoResearcher API",
        "docs": "/docs",
        "health": "/health",
        "research": "/research",
        "model": OLLAMA_MODEL,
    }
