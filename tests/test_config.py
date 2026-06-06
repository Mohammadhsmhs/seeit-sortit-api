from config import get_llm


def test_get_llm_uses_litellm_model_env_var(monkeypatch) -> None:
    monkeypatch.setenv("LITELLM_MODEL", "nebius/Qwen/Qwen2.5-VL-72B-Instruct")
    monkeypatch.setenv("LITELLM_API_BASE", "https://api.studio.nebius.com/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "test-key")

    llm = get_llm()

    assert llm.model == "nebius/Qwen/Qwen2.5-VL-72B-Instruct"
    assert llm.api_key == "test-key"


def test_get_llm_defaults_to_ollama_llava(monkeypatch) -> None:
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    monkeypatch.delenv("LITELLM_API_BASE", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)

    llm = get_llm()

    assert llm.model == "ollama/llava"
    assert llm.api_key == "no-key"
