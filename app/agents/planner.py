"""
app/agents/planner.py
Planner agent: decomposes the user query into focused literature search sub-questions.
Uses Ollama structured JSON output via LangChain.
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


class PlannerOutput(BaseModel):
    sub_questions: List[str] = Field(description="3 to 5 focused literature search sub-questions")


def _get_llm():
    llm = ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0,
    )
    return llm.with_structured_output(PlannerOutput)


def planner_node(state: ResearchState):
    query = state["query"]
    cycle = state.get("cycle", 0)
    gaps = state.get("gaps", [])

    prompt = f"""
You are a research planning agent for scientific literature reviews.

Task:
Break the user's research topic into 3 to 5 short, high-value literature search sub-questions.
Each sub-question should be optimized for retrieving scientific papers.

Rules:
- Keep each sub-question concise.
- Focus on methods, benchmarks, datasets, limitations, comparisons, or recent advances.
- Avoid redundancy.
- If critique gaps are provided, incorporate them.
- Return only structured output.

User query:
{query}

Current cycle:
{cycle}

Gap hints from critic:
{gaps}
""".strip()

    llm = _get_llm()
    result = llm.invoke(prompt)

    sub_questions = [q.strip() for q in result.sub_questions if q.strip()]
    sub_questions = sub_questions[:5]

    print(f"[Planner] Cycle {cycle} produced {len(sub_questions)} sub-questions")
    for i, q in enumerate(sub_questions, 1):
        print(f"  {i}. {q}")

    return {
        "sub_questions": sub_questions,
        "cycle": cycle + 1,
    }
