import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv()

lf = Langfuse()  # v4: direct instantiation, not get_client()

DATASET_NAME = "autoresearcher-eval"

try:
    lf.create_dataset(name=DATASET_NAME, description="Eval set for AutoResearcher")
    print(f"Created dataset: {DATASET_NAME}")
except Exception as e:
    print(f"Dataset may already exist: {e}")

ITEMS = [
    {
        "input": {
            "query": "What are the latest advances in transformer-based LLMs?",
            "max_papers": 20,
            "max_cycles": 3,
        },
        "expected_output": {
            "must_include_keywords": ["attention", "transformer", "fine-tuning", "GPT", "BERT"],
        },
    },
    {
        "input": {
            "query": "How does retrieval-augmented generation improve factual accuracy?",
            "max_papers": 15,
            "max_cycles": 2,
        },
        "expected_output": {
            "must_include_keywords": ["retrieval", "RAG", "hallucination", "vector", "grounding"],
        },
    },
]

for item in ITEMS:
    lf.create_dataset_item(
        dataset_name=DATASET_NAME,
        input=item["input"],
        expected_output=item["expected_output"],
    )

lf.flush()
print(f"Seeded {len(ITEMS)} items into '{DATASET_NAME}'")