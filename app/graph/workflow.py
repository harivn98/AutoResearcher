"""
app/graph/workflow.py

LangGraph StateGraph — cyclic multi-agent research pipeline.

Flow:
    START
      │
      ▼
   [planner]  ──────────────────────────────────────────────────────┐
      │                                                              │
      ▼                                                         (gap found
   [retriever]                                                 & cycles left)
      │                                                              │
      ▼                                                              │
   [critic] ── approved ──▶ [synthesizer] ──▶ END                   │
      │                                                              │
      └──── gaps found ─────────────────────────────────────────────┘
              (re-plan with gap sub-questions)

All nodes receive/return ResearchState.
Langfuse tracing is injected at .invoke() time via callbacks config.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.graph.state import ResearchState
from app.agents.planner     import planner_node
from app.agents.retriever   import retriever_node
from app.agents.critic      import critic_node
from app.agents.synthesizer import synthesizer_node


# ── Conditional edge: after Critic, route to Synthesizer or back to Planner ──

def route_after_critic(state: ResearchState) -> str:
    """
    Decision function for the conditional edge after the Critic node.

    Returns:
        "synthesize"  → coverage_score >= threshold OR max cycles reached
        "replan"      → gaps exist and cycles remaining
    """
    approved      = state.get("approved", False)
    cycle         = state.get("cycle", 0)
    max_cycles    = state.get("max_cycles", 3)

    if approved:
        print(f"[Router] ✅ Critic approved (score={state.get('coverage_score', 0):.2f}) → Synthesizer")
        return "synthesize"

    if cycle >= max_cycles:
        print(f"[Router] ⚠️  Max cycles ({max_cycles}) reached → forcing Synthesizer")
        return "synthesize"

    print(f"[Router] 🔄 Gaps found (cycle {cycle}/{max_cycles}) → re-planning")
    return "replan"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_graph() -> CompiledStateGraph:
    """
    Construct and compile the AutoResearcher StateGraph.

    Node wiring:
        START → planner → retriever → critic
        critic → [conditional] → synthesizer → END
                              └→ planner  (re-plan with gaps)
    """
    builder = StateGraph(ResearchState)

    # Register nodes
    builder.add_node("planner",     planner_node)
    builder.add_node("retriever",   retriever_node)
    builder.add_node("critic",      critic_node)
    builder.add_node("synthesizer", synthesizer_node)

    # Linear edges
    builder.add_edge(START,       "planner")
    builder.add_edge("planner",   "retriever")
    builder.add_edge("retriever", "critic")

    # Conditional edge after Critic
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "synthesize": "synthesizer",
            "replan":     "planner",
        },
    )

    # Terminal edge
    builder.add_edge("synthesizer", END)

    return builder.compile()


# ── Convenience run function (used by FastAPI) ────────────────────────────────

def run_research(
    query: str,
    max_cycles: int = 3,
    max_papers: int = 20,
    langfuse_handler=None,
) -> ResearchState:
    """
    Execute the full research pipeline for a given query.

    Args:
        query:             User research query
        max_cycles:        Max Critic→Planner re-planning loops
        max_papers:        Max papers fetched per Retriever cycle
        langfuse_handler:  Optional Langfuse CallbackHandler for tracing

    Returns:
        Final ResearchState with report, sources, coverage_score, cycle count
    """
    graph = build_graph()

    initial_state: ResearchState = {
        "query":           query,
        "max_cycles":      max_cycles,
        "max_papers":      max_papers,
        "sub_questions":   [],
        "papers":          [],
        "retrieval_stats": {},
        "coverage_score":  0.0,
        "gaps":            [],
        "critic_feedback": "",
        "cycle":           0,
        "approved":        False,
        "report":          "",
        "sources":         [],
    }

    config = {}
    if langfuse_handler:
        config = {"callbacks": [langfuse_handler]}

    print(f"\n{'='*60}")
    print(f"[AutoResearcher] Starting research: {query!r}")
    print(f"[AutoResearcher] max_cycles={max_cycles}, max_papers={max_papers}")
    print(f"{'='*60}\n")

    final_state = graph.invoke(initial_state, config=config)

    print(f"\n{'='*60}")
    print(f"[AutoResearcher] Done! Cycles: {final_state.get('cycle', 0)}")
    print(f"[AutoResearcher] Coverage score: {final_state.get('coverage_score', 0):.2f}")
    print(f"[AutoResearcher] Sources cited: {len(final_state.get('sources', []))}")
    print(f"{'='*60}\n")

    return final_state
