"""
app/graph/state.py
Typed state shared across all LangGraph agent nodes.
"""

from typing import List, Dict, Any, Optional, Annotated
from typing_extensions import TypedDict
import operator


class ResearchState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────────────
    query: str                          # Original user research query
    max_cycles: int                     # Max allowed Critic→Planner loops
    max_papers: int                     # Max papers to fetch per cycle

    # ── Planner output ───────────────────────────────────────────────────────
    sub_questions: List[str]            # Decomposed sub-questions

    # ── Retriever output ─────────────────────────────────────────────────────
    papers: Annotated[List[Dict[str, Any]], operator.add]   # Accumulates across cycles
    retrieval_stats: Dict[str, int]     # {"added": N, "skipped": N}

    # ── Critic output ────────────────────────────────────────────────────────
    coverage_score: float               # 0.0 – 1.0
    gaps: List[str]                     # Gap sub-questions for next cycle
    critic_feedback: str                # Human-readable critique

    # ── Cycle tracking ───────────────────────────────────────────────────────
    cycle: int                          # Current iteration count
    approved: bool                      # True when Critic is satisfied

    # ── Synthesizer output ───────────────────────────────────────────────────
    report: str                         # Final Markdown report
    sources: List[Dict[str, Any]]       # Cited papers
