"""Small model-to-provider registry for Claude Ensemble."""

from __future__ import annotations

from collections.abc import Mapping

from .anthropic import AnthropicProvider
from .google import GoogleProvider
from .model_provider import ModelProvider


class ProviderRegistry:
    """Resolve a selected model to its provider without provider API logic."""

    def __init__(
        self,
        providers: Mapping[str, ModelProvider] | None = None,
    ) -> None:
        self.providers = dict(providers or {})
        self.providers.setdefault("anthropic", AnthropicProvider())
        self.providers.setdefault("google", GoogleProvider())

    def register(self, name: str, provider: ModelProvider) -> None:
        self.providers[name] = provider

    def resolve(self, model: str) -> ModelProvider:
        normalized = model.lower()
        if normalized.startswith(("claude-", "claude_", "haiku", "sonnet", "opus")):
            provider_name = "anthropic"
        elif normalized.startswith(("gemini-", "gemini_", "models/gemini-")):
            provider_name = "google"
        else:
            raise ValueError(
                f"No provider mapping for model {model!r}; register it explicitly"
            )
        try:
            return self.providers[provider_name]
        except KeyError as exc:
            raise ValueError(
                f"Provider {provider_name!r} is not registered for model {model!r}"
            ) from exc
