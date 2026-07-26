"""Human-readable model labels and color coding for the UI."""

from __future__ import annotations

MODEL_COLORS: dict[str, dict[str, str]] = {
    "grok": {
        "provider": "xAI",
        "color": "blue",
        "badge": "bg-blue-900/60 text-blue-200 border-blue-500/40",
        "dot": "bg-blue-400",
    },
    "claude": {
        "provider": "Anthropic",
        "color": "orange",
        "badge": "bg-orange-900/60 text-orange-200 border-orange-500/40",
        "dot": "bg-orange-400",
    },
    "gpt": {
        "provider": "OpenAI",
        "color": "green",
        "badge": "bg-emerald-900/60 text-emerald-200 border-emerald-500/40",
        "dot": "bg-emerald-400",
    },
    "deepseek": {
        "provider": "DeepSeek",
        "color": "purple",
        "badge": "bg-purple-900/60 text-purple-200 border-purple-500/40",
        "dot": "bg-purple-400",
    },
    "llama": {
        "provider": "Meta",
        "color": "indigo",
        "badge": "bg-indigo-900/60 text-indigo-200 border-indigo-500/40",
        "dot": "bg-indigo-400",
    },
}

DEFAULT_COLOR = {
    "provider": "OpenRouter",
    "color": "gray",
    "badge": "bg-gray-800/60 text-gray-300 border-gray-500/40",
    "dot": "bg-gray-400",
}

DISPLAY_OVERRIDES: dict[str, str] = {
    "anthropic/claude-sonnet-4": "Claude Sonnet 4",
    "x-ai/grok-3": "Grok 3",
    "openai/gpt-4.1": "GPT-4.1",
    "x-ai/grok-4": "Grok 4",
    "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
}


def _normalize_model_id(model: str) -> str:
    return model.removeprefix("openrouter/").removeprefix("xai/").removeprefix("xai/")


def detect_provider_key(model: str) -> str:
    normalized = _normalize_model_id(model).lower()
    if "grok" in normalized or "x-ai" in normalized:
        return "grok"
    if "claude" in normalized or "anthropic" in normalized:
        return "claude"
    if "gpt" in normalized or "openai" in normalized:
        return "gpt"
    if "deepseek" in normalized:
        return "deepseek"
    if "llama" in normalized:
        return "llama"
    return "default"


def format_model_display(model: str) -> str:
    normalized = _normalize_model_id(model)
    if normalized in DISPLAY_OVERRIDES:
        return DISPLAY_OVERRIDES[normalized]
    parts = normalized.replace("_", "-").split("/")
    name = parts[-1] if parts else normalized
    return name.replace("-", " ").title()


def get_model_style(model: str) -> dict[str, str]:
    key = detect_provider_key(model)
    if key == "default":
        return {**DEFAULT_COLOR}
    return {**MODEL_COLORS[key]}
