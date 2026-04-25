"""
app/rag/chroma_store.py
ChromaDB RAG backend with local sentence-transformers embeddings.
No API key required — fully open-source.
"""

import os
import hashlib
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
PERSIST_DIR   = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION    = os.getenv("CHROMA_COLLECTION", "autoresearcher_papers")
EMBED_MODEL   = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")  # 80 MB, fast & accurate
TOP_K_DEFAULT = int(os.getenv("TOP_K_DEFAULT", "10"))


# ── Singleton embedder (loaded once at import time) ───────────────────────────
_embedder: Optional[SentenceTransformer] = None

def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        print(f"[ChromaStore] Loading embedding model: {EMBED_MODEL}")
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


# ── ChromaDB client ───────────────────────────────────────────────────────────
def get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(
        path=PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )

def get_collection() -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},   # cosine similarity for paper embeddings
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_doc_id(paper: Dict[str, Any]) -> str:
    """Stable ID from arXiv ID or content hash — prevents duplicate ingestion."""
    arxiv_id = paper.get("arxiv_id") or paper.get("id", "")
    if arxiv_id:
        return arxiv_id.replace("/", "_")
    content = f"{paper.get('title', '')}{paper.get('abstract', '')}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def _build_text(paper: Dict[str, Any]) -> str:
    """Concatenate title + abstract for embedding — richer semantic signal."""
    title    = paper.get("title", "").strip()
    abstract = paper.get("abstract", "").strip()
    return f"{title}. {abstract}"


# ── Core API ──────────────────────────────────────────────────────────────────
def ingest_papers(papers: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Embed and store a list of papers into ChromaDB.
    Skips duplicates automatically via stable doc IDs.

    Args:
        papers: List of dicts with keys:
                  title, abstract, authors, year, arxiv_id, url

    Returns:
        {"added": N, "skipped": N}
    """
    if not papers:
        return {"added": 0, "skipped": 0}

    collection = get_collection()
    embedder   = get_embedder()

    # Filter out already-stored papers
    all_ids     = [_make_doc_id(p) for p in papers]
    existing    = set(collection.get(ids=all_ids)["ids"])
    new_papers  = [(p, id_) for p, id_ in zip(papers, all_ids) if id_ not in existing]

    if not new_papers:
        return {"added": 0, "skipped": len(papers)}

    texts, ids, metadatas = [], [], []
    for paper, doc_id in new_papers:
        texts.append(_build_text(paper))
        ids.append(doc_id)
        metadatas.append({
            "title":    paper.get("title", ""),
            "authors":  ", ".join(paper.get("authors", [])) if isinstance(paper.get("authors"), list) else paper.get("authors", ""),
            "year":     str(paper.get("year", "")),
            "arxiv_id": paper.get("arxiv_id", ""),
            "url":      paper.get("url", ""),
        })

    embeddings = embedder.encode(texts, show_progress_bar=False).tolist()

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    print(f"[ChromaStore] Ingested {len(new_papers)} papers | Skipped {len(papers) - len(new_papers)} duplicates")
    return {"added": len(new_papers), "skipped": len(papers) - len(new_papers)}


def semantic_search(
    query: str,
    top_k: int = TOP_K_DEFAULT,
    year_min: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Embed the query and return the top-k most similar papers.

    Args:
        query:    Natural language search query
        top_k:    Number of results to return
        year_min: Optional filter — only return papers from this year onwards

    Returns:
        List of result dicts with keys: title, abstract, authors, year,
        arxiv_id, url, similarity_score
    """
    collection = get_collection()
    embedder   = get_embedder()

    # Build optional metadata filter
    where = {"year": {"$gte": str(year_min)}} if year_min else None

    query_embedding = embedder.encode([query], show_progress_bar=False).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count() or 1),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        similarity = round(1 - dist, 4)   # cosine distance → similarity
        output.append({
            "title":            meta.get("title", ""),
            "abstract":         doc.split(". ", 1)[-1] if ". " in doc else doc,
            "authors":          meta.get("authors", ""),
            "year":             meta.get("year", ""),
            "arxiv_id":         meta.get("arxiv_id", ""),
            "url":              meta.get("url", ""),
            "similarity_score": similarity,
        })

    # Sort by similarity descending (ChromaDB returns by distance ascending)
    output.sort(key=lambda x: x["similarity_score"], reverse=True)
    return output


def deduplicate(papers: List[Dict[str, Any]], threshold: float = 0.92) -> List[Dict[str, Any]]:
    """
    Remove near-duplicate papers using pairwise cosine similarity.
    Keeps the paper with the higher similarity_score when duplicates are found.

    Args:
        papers:    List of paper dicts (output of semantic_search)
        threshold: Cosine similarity above which two papers are considered duplicates

    Returns:
        Deduplicated list of papers
    """
    if len(papers) <= 1:
        return papers

    embedder = get_embedder()
    texts    = [f"{p['title']}. {p['abstract']}" for p in papers]
    embeds   = embedder.encode(texts, show_progress_bar=False)

    # Pairwise cosine similarity
    from numpy import dot
    from numpy.linalg import norm

    def cosine(a, b):
        return dot(a, b) / (norm(a) * norm(b) + 1e-8)

    kept    = []
    removed = set()
    for i, paper in enumerate(papers):
        if i in removed:
            continue
        kept.append(paper)
        for j in range(i + 1, len(papers)):
            if j not in removed:
                if cosine(embeds[i], embeds[j]) >= threshold:
                    removed.add(j)

    print(f"[ChromaStore] Deduplication: {len(papers)} → {len(kept)} papers")
    return kept


def collection_stats() -> Dict[str, Any]:
    """Return basic stats about the current ChromaDB collection."""
    collection = get_collection()
    count = collection.count()
    return {
        "collection": COLLECTION,
        "total_papers": count,
        "persist_dir": PERSIST_DIR,
        "embed_model": EMBED_MODEL,
    }


def reset_collection() -> None:
    """Drop and recreate the collection. Use carefully — deletes all stored papers."""
    client = get_chroma_client()
    client.delete_collection(COLLECTION)
    get_collection()
    print(f"[ChromaStore] Collection '{COLLECTION}' reset.")
