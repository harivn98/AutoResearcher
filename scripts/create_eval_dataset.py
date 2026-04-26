from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv()
lf = Langfuse()  # takes keys from .env

DATASET_NAME = "autoresearcher/video-transformers-eval"

items = [
    {
        "input": {
            "query": "transformer architectures for video understanding",
            "max_papers": 12,
            "max_cycles": 2,
        },
        "expected_output": {
            "must_include_keywords": [
                "Video Swin",
                "InternVideo",
                "spatiotemporal",
                "action recognition",
            ]
        },
        "metadata": {"topic": "video", "difficulty": "medium"},
    },
    {
        "input": {
            "query": "retrieval-augmented generation for scientific literature review",
            "max_papers": 20,
            "max_cycles": 3,
        },
        "expected_output": {
            "must_include_keywords": [
                "RAG",
                "vector store",
                "retriever",
                "hallucination",
            ]
        },
        "metadata": {"topic": "rag", "difficulty": "medium"},
    },
]

dataset = lf.create_dataset(
    name=DATASET_NAME,
    description="AutoResearcher evaluation set for literature-review quality",
    metadata={"app": "autoresearcher"},
)

for item in items:
    lf.create_dataset_item(
        dataset_name=DATASET_NAME,
        input=item["input"],
        expected_output=item["expected_output"],
        metadata=item["metadata"],
    )

print("Created dataset:", DATASET_NAME)