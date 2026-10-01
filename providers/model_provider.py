"""Canonical model-provider contract used by Ensemble workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelRequest:
    """A provider-neutral model invocation."""

    prompt: str
    model: str | None = None
    system_prompt: str | None = None
    timeout: float = 300.0

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt:
            raise ValueError("prompt must be a non-empty string")
        if self.model is not None and not isinstance(self.model, str):
            raise ValueError("model must be a string or None")
        if self.system_prompt is not None and not isinstance(self.system_prompt, str):
            raise ValueError("system_prompt must be a string or None")
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")


@dataclass(frozen=True)
class ModelResponse:
    """Normalized provider response plus provider-specific metadata."""

    provider: str
    model: str
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: float | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class ModelProvider(ABC):
    """Minimal contract implemented by every Ensemble model provider."""

    @abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate one response for a provider-neutral request."""
        raise NotImplementedError
