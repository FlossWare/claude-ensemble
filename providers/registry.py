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

    def _provider(self, name: str) -> ModelProvider:
        """Return a provider, constructing the built-in adapter only on demand."""
        if name not in self.providers:
            if name == "anthropic":
                self.providers[name] = AnthropicProvider()
            elif name == "google":
                self.providers[name] = GoogleProvider()
        if name not in self.providers:
            raise ValueError(f"Provider {name!r} is not registered")
        return self.providers[name]

    def register(self, name: str, provider: ModelProvider) -> None:
        self.providers[name] = provider

    def resolve(self, model: str) -> ModelProvider:
        provider_name, _ = self.resolve_model(model)
        return self._provider(provider_name)

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

        self._provider(provider_name)
        return provider_name, canonical
