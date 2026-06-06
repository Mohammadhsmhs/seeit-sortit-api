import logging
import os

from langchain_litellm import ChatLiteLLM

logger = logging.getLogger(__name__)


def get_langfuse_handler():
    """Return a Langfuse CallbackHandler if credentials are configured, else None.

    Required environment variables:
      LANGFUSE_PUBLIC_KEY  — project public key
      LANGFUSE_SECRET_KEY  — project secret key
      LANGFUSE_HOST        — (optional) self-hosted instance URL
    """
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not (public_key and secret_key):
        return None

    try:
        from langfuse.langchain import CallbackHandler  # type: ignore[import]

        return CallbackHandler()
    except Exception as exc:
        logger.warning("Langfuse tracing unavailable: %s", exc)
        return None


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
