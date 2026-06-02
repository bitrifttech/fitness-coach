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


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    model_id: str
    confidence_threshold: float
    base_url: str = OPENROUTER_BASE_URL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return Settings(
        openrouter_api_key=api_key,
        model_id=os.getenv("MODEL_ID", "openai/gpt-4o-mini").strip(),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.6")),
    )
