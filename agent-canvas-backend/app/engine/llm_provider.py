from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI


def build_chat_model(config: dict[str, Any], *, temperature: float | int | None = None):
    provider = str(config.get("provider") or "OpenAI").lower()
    model = config.get("model") or _default_model(provider)
    api_key = config.get("api_key") or config.get("apiKey")
    base_url = config.get("base_url") or config.get("baseUrl")
    headers = _headers_to_dict(config.get("custom_headers") or config.get("headers"))
    temperature = config.get("temperature", temperature if temperature is not None else 0)

    if provider in {"openai", "custom"}:
        _require_node_api_key(api_key, config.get("provider") or "OpenAI")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url or None,
            default_headers=headers or None,
        )
    if provider in {"gemini", "google", "google gemini"}:
        _require_node_api_key(api_key, config.get("provider") or "Gemini")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise ImportError(
                "Gemini provider requires langchain-google-genai. Run `pip install -r requirements.txt`."
            ) from exc
        return ChatGoogleGenerativeAI(model=model, temperature=temperature, google_api_key=api_key)
    if provider in {"claude", "anthropic"}:
        _require_node_api_key(api_key, config.get("provider") or "Claude")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ImportError(
                "Claude provider requires langchain-anthropic. Run `pip install -r requirements.txt`."
            ) from exc
        return ChatAnthropic(model=model, temperature=temperature, api_key=api_key)
    raise ValueError(f"Unsupported LLM provider: {config.get('provider')}")


def _require_node_api_key(api_key: Any, provider: str) -> None:
    if isinstance(api_key, str) and api_key.strip():
        return
    raise ValueError(
        f"{provider} API key is required in the node config. "
        "Server environment variables are not used for LLM node credentials."
    )


def _default_model(provider: str) -> str:
    if provider in {"gemini", "google", "google gemini"}:
        return "gemini-1.5-flash"
    if provider in {"claude", "anthropic"}:
        return "claude-3-5-haiku-latest"
    return "gpt-4o-mini"


def _headers_to_dict(headers: Any) -> dict[str, str]:
    if isinstance(headers, dict):
        return {str(key): str(value) for key, value in headers.items() if key}
    if isinstance(headers, list):
        return {str(row.get("key")): str(row.get("value")) for row in headers if row.get("key")}
    return {}
