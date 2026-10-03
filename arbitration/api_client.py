#!/usr/bin/env python3
"""Compatibility facade over the canonical provider layer."""

from __future__ import annotations

import logging
import time
from typing import Any

from providers import ModelRequest, ModelResponse, ProviderRegistry

logger = logging.getLogger(__name__)


class MultiModelClient:
    """Unified direct API client backed by provider-neutral adapters."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry | None = None,
        cost_logger: Any | None = None,
        task_name: str = "multi_model_call",
    ):
        self.registry = registry or ProviderRegistry()
        self.cost_logger = cost_logger
        self.task_name = task_name

    def call_model(
        self,
        model: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Call a selected model and return its text response."""
        return self.call_model_response(
            model=model,
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        ).text

    def call_model_response(
        self,
        *,
        model: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 300.0,
        credential: str | None = None,
    ) -> ModelResponse:
        """Call a selected model and return the normalized provider response."""
        _, canonical_model = self.registry.resolve_model(model)
        provider = self.registry.resolve(model)
        started = time.monotonic()
        response = provider.generate(
            ModelRequest(
                prompt=prompt,
                model=canonical_model,
                system_prompt=system or None,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                metadata={"credential": credential} if credential else {},
            )
        )

        if self.cost_logger is not None:
            latency_ms = (time.monotonic() - started) * 1000
            self.cost_logger.log_call(
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                task_name=self.task_name,
                source="provider",
                provider=response.provider,
                metadata={
                    "request_id": response.request_id,
                    "latency_ms": latency_ms,
                    "provider_metadata": response.raw_metadata,
                },
                cost_usd=response.cost_usd,
            )
        return response

    def call_models_parallel(
        self,
        models: list[str],
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict[str, str]:
        """Call multiple models in parallel (returns model -> response)."""
        import concurrent.futures

        results: dict[str, str] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = {
                executor.submit(
                    self.call_model,
                    model,
                    prompt,
                    system,
                    temperature,
                    max_tokens,
                ): model
                for model in models
            }
            for future in concurrent.futures.as_completed(futures):
                model = futures[future]
                try:
                    results[model] = future.result()
                except Exception as exc:
                    logger.error("Error calling %s: %s", model, exc)
                    results[model] = f"ERROR: {exc}"
        return results
