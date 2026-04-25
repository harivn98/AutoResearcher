"""
app/observability/langfuse_client.py
Langfuse setup for LangChain/LangGraph callback tracing.
"""

import os
from dotenv import load_dotenv
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

load_dotenv()

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")


def is_langfuse_enabled() -> bool:
    return bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)


def init_langfuse() -> bool:
    """
    Initialize global Langfuse client once.
    Safe to call on startup.
    """
    if not is_langfuse_enabled():
        print("[Langfuse] Disabled — API keys not set")
        return False

    Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )
    print(f"[Langfuse] Enabled at {LANGFUSE_HOST}")
    return True


def get_langfuse_handler():
    """
    Return a LangChain-compatible callback handler.
    Returns None if Langfuse is not configured.
    """
    if not is_langfuse_enabled():
        return None
    return CallbackHandler()
