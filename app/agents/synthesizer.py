import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama

from app.graph.state import ResearchState

load_dotenv()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _get_llm():
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,
    )


def _format_sources(papers, limit=10):
    rows = []
    for i, p in enumerate(papers[:limit], 1):
        rows.append(
            f"[{i}] {p.get('title', '')} ({p.get('year', '')})\n"
            f"Authors: {p.get('authors', '')}\n"
            f"URL: {p.get('url', '')}\n"
            f"Abstract: {p.get('abstract', '')[:700]}"
        )
    return "\n\n".join(rows)


def synthesizer_node(state: ResearchState):
    query = state["query"]
    papers = state.get("papers", [])
    coverage_score = state.get("coverage_score", 0.0)
    critic_feedback = state.get("critic_feedback", "")

    if not papers:
        return {
            "report": "# Literature Review\n\nNo relevant papers were found.",
            "sources": [],
        }

    prompt = f"""
You are a scientific synthesis agent.

Write a concise markdown literature review based only on the provided papers.

Requirements:
- Use these sections:
  1. Overview
  2. Key Methods
  3. Main Findings
  4. Limitations and Gaps
  5. Selected Sources
- Be factual and avoid inventing claims.
- Mention disagreements or uncertainty if coverage is incomplete.
- In "Selected Sources", list the most relevant papers with title and year.
- Keep the writing clear and professional.

User query:
{query}

Coverage score:
{coverage_score}

Critic feedback:
{critic_feedback}

Source papers:
{_format_sources(papers)}
""".strip()

    llm = _get_llm()
    response = llm.invoke(prompt)
    report = response.content if hasattr(response, "content") else str(response)

    return {
        "report": report.strip(),
        "sources": papers[:10],
    }