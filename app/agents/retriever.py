"""
app/agents/retriever.py
Retriever agent: fetches papers from arXiv, stores them in ChromaDB,
performs semantic search, ranking, and deduplication.
"""

from typing import List, Dict, Any

from app.graph.state import ResearchState
from app.rag.arxiv_fetcher import fetch_multi_query
from app.rag.chroma_store import ingest_papers, semantic_search, deduplicate


def retriever_node(state: ResearchState):
    query = state["query"]
    sub_questions = state.get("sub_questions", [])
    max_papers = state.get("max_papers", 20)

    if not sub_questions:
        sub_questions = [query]

    per_query = max(3, max_papers // max(1, len(sub_questions)))

    fetched = fetch_multi_query(
        queries=sub_questions,
        max_per_query=per_query,
    )

    stats = ingest_papers(fetched)
    ranked = semantic_search(query=query, top_k=max_papers)
    final_papers = deduplicate(ranked, threshold=0.92)

    print(f"[Retriever] fetched={len(fetched)} ranked={len(ranked)} final={len(final_papers)}")

    return {
        "papers": final_papers,
        "retrieval_stats": stats,
    }
