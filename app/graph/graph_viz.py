"""
app/graph/graph_viz.py
Utility to render the compiled LangGraph as a Mermaid diagram.
Run directly: python -m app.graph.graph_viz
"""

from app.graph.workflow import build_graph

def print_mermaid():
    graph = build_graph()
    try:
        mermaid = graph.get_graph().draw_mermaid()
        print("── Mermaid diagram ──────────────────────────────────")
        print(mermaid)
    except Exception as e:
        print(f"Mermaid render failed: {e}")
        print("Graph nodes:", [n for n in graph.get_graph().nodes])

if __name__ == "__main__":
    print_mermaid()
