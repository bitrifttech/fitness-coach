"""OpenRouter chat-model factory.

OpenRouter exposes an OpenAI-compatible API, so we use ``ChatOpenAI`` pointed at
the OpenRouter base URL. The model id is configurable; it must be a model that
supports tool/function calling, since both routing (``with_structured_output``)
and the generator agent depend on it.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from .config import get_settings


@lru_cache(maxsize=4)
def get_chat_model(temperature: float = 0.0) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_id,
        temperature=temperature,
        api_key=settings.openrouter_api_key,
        base_url=settings.base_url,
        default_headers={
            # Optional attribution headers recommended by OpenRouter.
            "HTTP-Referer": "https://github.com/fitness-coach",
            "X-Title": "Fitness Coach Multi-Agent",
        },
    )
