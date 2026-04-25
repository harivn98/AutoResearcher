"""
app/agents/critic.py
Critic agent: evaluates retrieval quality, identifies research gaps,
and decides whether another cycle is needed.
"""

import os
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

from app.graph.state import ResearchState

load_dotenv()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
CRITIC_THRESHOLD = float(os.getenv("CRITIC_THRESHOLD", "0.75"))


class CriticOutput(BaseModel):
    coverage_score: float = Field(description="A score from 0.0 to 1.0")
    approved: bool = Field(description="True if evidence is sufficient for synthesis")
    gaps: List[str] = Field(description="Missing angles or follow-up sub-questions")
    critic_feedback: str = Field(description="Short explanation of strengths and weaknesses")


def _get_llm():
    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,
    )
    return llm.with_structured_output(CriticOutput)


def _format_papers(papers, limit=8):
    lines = []
    for i, p in enumerate(papers[:limit], 1):
        lines.append(
            f"{i}. {p.get('title', '')} ({p.get('year', '')}) | score={p.get('similarity_score', '')}\n"
            f"   Authors: {p.get('authors', '')}\n"
            f"   Abstract: {p.get('abstract', '')[:500]}"
        )
    return "\n\n".join(lines)


def critic_node(state: ResearchState):
    query = state["query"]
    papers = state.get("papers", [])
    cycle = state.get("cycle", 1)
    max_cycles = state.get("max_cycles", 3)

    if not papers:
        return {
            "coverage_score": 0.0,
            "approved": False,
            "gaps": [f"core papers for: {query}"],
            "critic_feedback": "No papers were retrieved.",
        }

    prompt = f"""
You are a critic agent for an academic literature analysis system.

Evaluate whether the retrieved papers sufficiently cover the user's research query.

Scoring guidance:
- 0.0 to 0.4: weak, irrelevant, or too sparse
- 0.5 to 0.74: partial coverage, important gaps remain
- 0.75 to 1.0: sufficient for synthesis

Rules:
- Approve only if the results are relevant and reasonably complete.
- If coverage is weak, propose 1 to 3 specific gap queries.
- Keep feedback concise and actionable.
- Return only structured output.

User query:
{query}

Current cycle:
{cycle} / {max_cycles}

Retrieved papers:
{_format_papers(papers)}
""".strip()

    llm = _get_llm()
    result = llm.invoke(prompt)

    coverage = max(0.0, min(1.0, float(result.coverage_score)))
    approved = bool(result.approved) and coverage >= CRITIC_THRESHOLD
    gaps = [g.strip() for g in result.gaps if g.strip()][:3]

    print(f"[Critic] coverage={coverage:.2f} approved={approved} threshold={CRITIC_THRESHOLD}")
    if gaps:
        print(f"[Critic] gaps={gaps}")

    return {
        "coverage_score": coverage,
        "approved": approved,
        "gaps": gaps,
        "critic_feedback": result.critic_feedback.strip(),
    }
