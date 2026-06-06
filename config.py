import os

from langchain_litellm import ChatLiteLLM


def get_llm() -> ChatLiteLLM:
    """Build a ChatLiteLLM instance from environment variables.

    Environment variables:
      LITELLM_MODEL     — model identifier (default: ollama/llava)
      LITELLM_API_BASE  — base URL for the model endpoint (optional)
      LITELLM_API_KEY   — API key (default: no-key, safe for local models)
    """
    model = os.environ.get("LITELLM_MODEL", "ollama/llava")
    api_base = os.environ.get("LITELLM_API_BASE")
    api_key = os.environ.get("LITELLM_API_KEY", "no-key")

    kwargs: dict[str, str] = {"model": model, "api_key": api_key}
    if api_base:
        kwargs["api_base"] = api_base

    return ChatLiteLLM(**kwargs)
