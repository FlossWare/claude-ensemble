"""Small model-to-provider registry for Claude Ensemble."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .anthropic import AnthropicProvider
from .google import GoogleProvider
from .model_provider import ModelProvider


class ProviderRegistry:
    """Resolve a model to its provider and canonical API model."""

    _ANTHROPIC_ALIASES = {
        "haiku": "CLAUDE_HAIKU_MODEL",
        "sonnet": "CLAUDE_SONNET_MODEL",
        "opus": "CLAUDE_OPUS_MODEL",
    }
    _DEFAULT_ANTHROPIC_MODELS = {
        "haiku": "claude-haiku-4-5",
        "sonnet": "claude-sonnet-5",
        "opus": "claude-opus-5",
    }

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
        provider_name, _ = self.resolve_model(model)
        return self.providers[provider_name]

    def resolve_model(self, model: str) -> tuple[str, str]:
        """Return the provider name and API model ID for a selected model."""
        normalized = model.lower()
        if normalized in self._ANTHROPIC_ALIASES:
            provider_name = "anthropic"
            env_name = self._ANTHROPIC_ALIASES[normalized]
            canonical = os.environ.get(
                env_name, self._DEFAULT_ANTHROPIC_MODELS[normalized]
            )
        elif normalized.startswith(("claude-", "claude_")):
            provider_name = "anthropic"
            canonical = model
        elif normalized.startswith(("gemini-", "gemini_", "models/gemini-")):
            provider_name = "google"
            canonical = model
        else:
            raise ValueError(
                f"No provider mapping for model {model!r}; register it explicitly"
            )

        if provider_name not in self.providers:
            raise ValueError(
                f"Provider {provider_name!r} is not registered for model {model!r}"
            )
        return provider_name, canonical
