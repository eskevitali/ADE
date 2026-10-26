"""Model-agnostic LLM provider with caching and provider fallback."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI

from ade.core.config import ADEConfig, LLMProvider, get_config

logger = logging.getLogger(__name__)

_model_cache: dict[tuple[str, str | None, float], BaseChatModel] = {}


class FallbackChatModel(BaseChatModel):
    """Try multiple underlying chat models in order until one succeeds."""

    models: list[BaseChatModel]
    provider_names: list[str]

    @property
    def _llm_type(self) -> str:
        return "ade-fallback-chat"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_error: Exception | None = None
        for name, model in zip(self.provider_names, self.models, strict=True):
            try:
                result = model._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                logger.debug("LLM response via %s", name)
                return result
            except Exception as exc:
                last_error = exc
                logger.warning("LLM provider %s failed: %s", name, exc)
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}") from last_error


def _normalize_model_name(model: str, provider: LLMProvider) -> str:
    if provider == LLMProvider.XAI:
        return model.removeprefix("xai/").removeprefix("openrouter/x-ai/")
    return model.removeprefix("openrouter/").removeprefix("xai/")


def _create_single_llm(
    config: ADEConfig,
    provider: LLMProvider,
    model: str,
    temperature: float,
) -> BaseChatModel:
    model_name = _normalize_model_name(model, provider)

    if provider == LLMProvider.XAI:
        if not config.has_xai():
            raise ValueError("XAI_API_KEY is not set")
        return ChatOpenAI(
            model=model_name,
            api_key=config.xai_api_key,
            base_url="https://api.x.ai/v1",
            temperature=temperature,
        )

    if not config.has_openrouter():
        raise ValueError("OPENROUTER_API_KEY is not set")
    return ChatOpenAI(
        model=model_name,
        api_key=config.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        default_headers={
            "HTTP-Referer": f"https://{config.domain}",
            "X-Title": "ADE v4",
        },
    )


def _provider_chain(model: str, preferred: LLMProvider | None) -> list[LLMProvider]:
    if preferred is not None:
        primary, secondary = preferred, (
            LLMProvider.XAI if preferred == LLMProvider.OPENROUTER else LLMProvider.OPENROUTER
        )
    elif model.startswith(("xai/", "openrouter/x-ai/")):
        primary, secondary = LLMProvider.XAI, LLMProvider.OPENROUTER
    else:
        primary, secondary = LLMProvider.OPENROUTER, LLMProvider.XAI

    config = get_config()
    chain: list[LLMProvider] = []
    for provider in (primary, secondary):
        if provider == LLMProvider.OPENROUTER and config.has_openrouter():
            chain.append(provider)
        elif provider == LLMProvider.XAI and config.has_xai():
            chain.append(provider)
    return chain


def _build_llm(
    model: str,
    *,
    provider: LLMProvider | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    config = get_config()
    temp = temperature if temperature is not None else config.default_temperature
    chain = _provider_chain(model, provider)

    if not chain:
        raise ValueError("No LLM API keys configured (OPENROUTER_API_KEY or XAI_API_KEY)")

    models = [_create_single_llm(config, p, model, temp) for p in chain]
    if len(models) == 1:
        return models[0]

    return FallbackChatModel(
        models=models,
        provider_names=[p.value for p in chain],
    )


def get_llm(
    model: str,
    *,
    provider: LLMProvider | None = None,
    temperature: float | None = None,
    use_cache: bool | None = None,
) -> BaseChatModel:
    """Return a chat model with optional caching and provider fallback."""
    config = get_config()
    temp = temperature if temperature is not None else config.default_temperature
    cache_enabled = config.llm_cache_enabled if use_cache is None else use_cache
    cache_key = (model, provider.value if provider else None, temp)

    if cache_enabled and cache_key in _model_cache:
        return _model_cache[cache_key]

    llm = _build_llm(model, provider=provider, temperature=temp)

    if cache_enabled:
        _model_cache[cache_key] = llm

    return llm


def clear_llm_cache() -> None:
    """Clear cached LLM instances (e.g. after key rotation)."""
    _model_cache.clear()
