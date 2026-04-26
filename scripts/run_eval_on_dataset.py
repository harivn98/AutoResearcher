"""
scripts/run_eval_on_dataset.py  —  SDK-version-agnostic
"""

import sys, os, uuid, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from langfuse import Langfuse
from dotenv import load_dotenv

from app.graph.workflow import run_research

load_dotenv()

LANGFUSE_PUBLIC_KEY = os.environ["LANGFUSE_PUBLIC_KEY"]
LANGFUSE_SECRET_KEY = os.environ["LANGFUSE_SECRET_KEY"]
LANGFUSE_HOST       = os.environ.get("LANGFUSE_HOST", "http://localhost:3000").rstrip("/")

DATASET_NAME = "autoresearcher-eval"
MODEL    = os.environ.get("OLLAMA_MODEL", "llama3.2")
RUN_NAME = f"{MODEL}-{datetime.now().strftime('%Y%m%d-%H%M')}"

AUTH = (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest(batch: list):
    resp = requests.post(
        f"{LANGFUSE_HOST}/api/public/ingestion",
        auth=AUTH,
        json={"batch": batch},
        timeout=30,
    )
    resp.raise_for_status()


def create_trace(trace_id: str, name: str, query: str):
    ingest([{
        "type": "trace-create",
        "id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "body": {
            "id": trace_id,
            "name": name,
            "input": {"query": query},
            "metadata": {"model": MODEL},
        },
    }])


def log_score(trace_id: str, score_name: str, value: float):
    ingest([{
        "type": "score-create",
        "id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "body": {
            "id": str(uuid.uuid4()),
            "traceId": trace_id,
            "name": score_name,
            "value": value,
            "dataType": "NUMERIC",
        },
    }])


def link_dataset_run(dataset_item_id: str, trace_id: str):
    """Link a trace to a dataset item run via REST API."""
    payload = {
        "runName": RUN_NAME,
        "datasetItemId": dataset_item_id,
        "traceId": trace_id,
    }
    resp = requests.post(
        f"{LANGFUSE_HOST}/api/public/dataset-run-items",
        auth=AUTH,
        json=payload,
        timeout=30,
    )
    if not resp.ok:
        print(f"     [WARN] link_dataset_run failed {resp.status_code}: {resp.text}")
    return resp.ok


def keyword_score(report: str, keywords: list) -> float:
    report_lower = report.lower()
    hits = sum(1 for k in keywords if k.lower() in report_lower)
    return round(hits / max(1, len(keywords)), 4)


lf = Langfuse()
print(f"Loading dataset: {DATASET_NAME}")
dataset = lf.get_dataset(DATASET_NAME)
print(f"Found {len(dataset.items)} items — run name: {RUN_NAME}\n")

results = []

for i, item in enumerate(dataset.items, 1):
    inp             = item.input
    expected        = item.expected_output or {}
    expected_kws    = expected.get("must_include_keywords", [])
    query           = inp["query"]
    dataset_item_id = item.id
    print(f"[{i}/{len(dataset.items)}] {query[:60]}...")
    print(f"     dataset_item_id={dataset_item_id}")

    trace_id = str(uuid.uuid4())
    create_trace(trace_id, RUN_NAME, query)

    coverage, kw_score = 0.0, 0.0
    try:
        state    = run_research(
            query=query,
            max_papers=inp.get("max_papers", 20),
            max_cycles=inp.get("max_cycles", 3),
        )
        report   = state.get("report", "")
        coverage = float(state.get("coverage_score", 0.0))
        kw_score = keyword_score(report, expected_kws)
        print(f"     coverage={coverage:.2f}  keywords={kw_score:.2f}  sources={len(state.get('sources', []))}")
        results.append({"query": query, "coverage": coverage, "keywords": kw_score})

    except Exception as e:
        print(f"     ERROR: {e}")

    log_score(trace_id, "coverage_score",    coverage)
    log_score(trace_id, "keyword_relevance", kw_score)
    link_dataset_run(dataset_item_id, trace_id)

avg_coverage = sum(r["coverage"] for r in results) / max(1, len(results))
avg_keywords = sum(r["keywords"] for r in results) / max(1, len(results))

print(f"\n{'='*60}")
print(f"Run:                   {RUN_NAME}")
print(f"Items evaluated:       {len(results)}/{len(dataset.items)}")
print(f"Avg coverage_score:    {avg_coverage:.3f}")
print(f"Avg keyword_relevance: {avg_keywords:.3f}")
print(f"{'='*60}")
print(f"\nView results: {LANGFUSE_HOST} → Datasets → {DATASET_NAME} → Runs")
