# app/observability/langfuse_client.py

import os
from langfuse.callback import CallbackHandler
from dotenv import load_dotenv

load_dotenv()

def get_langfuse_handler() -> CallbackHandler:
    """
    Returns a LangChain-compatible Langfuse callback handler.
    Inject this into any LangGraph .invoke() call via config={"callbacks": [handler]}.
    """
    return CallbackHandler(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ["LANGFUSE_HOST"],
    )