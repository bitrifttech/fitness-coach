"""Central configuration, loaded from the environment.

Keeping these as a single typed object (rather than scattered ``os.getenv``
calls) makes the tunable decisions explicit and swappable — the model id and
the routing confidence threshold are both reviewer-facing knobs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LANGSMITH_ENDPOINT = "https://api.smith.langchain.com"


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    model_id: str
    confidence_threshold: float
    base_url: str = OPENROUTER_BASE_URL
    langsmith_api_key: str = ""
    langsmith_project: str = "fitness-coach"
    langsmith_tracing: bool = False


def configure_observability() -> None:
    """Enable LangSmith tracing when ``LANGSMITH_API_KEY`` is present.

    LangGraph/LangChain auto-trace LLM and tool invocations when these env vars
    are set — no custom span wiring required for the baseline.
    """
    settings = get_settings()
    if not settings.langsmith_tracing:
        return
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGCHAIN_ENDPOINT", LANGSMITH_ENDPOINT)
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    langsmith_key = os.getenv("LANGSMITH_API_KEY", "").strip()
    tracing = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true", "yes")
    if langsmith_key and not tracing:
        tracing = True
    return Settings(
        openrouter_api_key=api_key,
        model_id=os.getenv("MODEL_ID", "openai/gpt-4o-mini").strip(),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.6")),
        langsmith_api_key=langsmith_key,
        langsmith_project=os.getenv("LANGCHAIN_PROJECT", "fitness-coach").strip(),
        langsmith_tracing=tracing and bool(langsmith_key),
    )
