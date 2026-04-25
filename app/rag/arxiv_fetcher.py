"""
app/rag/arxiv_fetcher.py
Fetches papers from the arXiv public API — no API key required.
Returns normalized paper dicts compatible with chroma_store.ingest_papers().
"""

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional


ARXIV_API   = "http://export.arxiv.org/api/query"
NS          = {"atom": "http://www.w3.org/2005/Atom",
               "arxiv": "http://arxiv.org/schemas/atom"}
RATE_LIMIT  = 3.0   # seconds between requests (arXiv ToS: max 1 req/3s)


def _parse_entry(entry: ET.Element) -> Dict[str, Any]:
    """Parse a single arXiv Atom entry into a normalized paper dict."""
    def text(tag: str) -> str:
        el = entry.find(tag, NS)
        return el.text.strip() if el is not None and el.text else ""

    arxiv_id = text("atom:id").split("/abs/")[-1]
    authors  = [
        a.find("atom:name", NS).text.strip()
        for a in entry.findall("atom:author", NS)
        if a.find("atom:name", NS) is not None
    ]
    published = text("atom:published")
    year      = published[:4] if published else ""
    pdf_url   = next(
        (l.get("href", "") for l in entry.findall("atom:link", NS)
         if l.get("type") == "application/pdf"),
        f"https://arxiv.org/pdf/{arxiv_id}"
    )

    return {
        "title":    text("atom:title").replace("\n", " "),
        "abstract": text("atom:summary").replace("\n", " "),
        "authors":  authors,
        "year":     year,
        "arxiv_id": arxiv_id,
        "url":      pdf_url,
    }


def fetch_papers(
    query: str,
    max_results: int = 20,
    sort_by: str = "relevance",   # "relevance" | "lastUpdatedDate" | "submittedDate"
    year_min: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Query arXiv and return normalized paper dicts.

    Args:
        query:       Search string (supports arXiv field prefixes: ti:, abs:, au:)
        max_results: Max papers to fetch (arXiv caps at 2000 per request)
        sort_by:     Sorting order
        year_min:    Optional — filter out papers older than this year

    Returns:
        List of paper dicts: title, abstract, authors, year, arxiv_id, url
    """
    params = urllib.parse.urlencode({
        "search_query": query,
        "start":        0,
        "max_results":  max_results,
        "sortBy":       sort_by,
        "sortOrder":    "descending",
    })
    url = f"{ARXIV_API}?{params}"

    print(f"[arXiv] Fetching: {query!r} (max={max_results})")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            xml_data = resp.read()
    except Exception as e:
        print(f"[arXiv] Request failed: {e}")
        return []

    time.sleep(RATE_LIMIT)   # respect arXiv rate limit

    root    = ET.fromstring(xml_data)
    entries = root.findall("atom:entry", NS)
    papers  = [_parse_entry(e) for e in entries]

    # Optional year filter
    if year_min:
        papers = [p for p in papers if p["year"] and int(p["year"]) >= year_min]

    print(f"[arXiv] Retrieved {len(papers)} papers")
    return papers


def fetch_multi_query(
    queries: List[str],
    max_per_query: int = 15,
    year_min: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch papers for multiple sub-queries (from the Planner agent).
    Automatically deduplicates by arxiv_id before returning.

    Args:
        queries:       List of sub-questions from Planner
        max_per_query: Max papers per sub-query
        year_min:      Optional year filter

    Returns:
        Combined, deduplicated list of paper dicts
    """
    seen_ids = set()
    all_papers: List[Dict[str, Any]] = []

    for q in queries:
        papers = fetch_papers(q, max_results=max_per_query, year_min=year_min)
        for paper in papers:
            key = paper.get("arxiv_id") or paper["title"]
            if key not in seen_ids:
                seen_ids.add(key)
                all_papers.append(paper)
        time.sleep(RATE_LIMIT)

    print(f"[arXiv] Total unique papers across {len(queries)} queries: {len(all_papers)}")
    return all_papers
