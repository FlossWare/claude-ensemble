"""Tests for provider selection and the compatibility client."""

from __future__ import annotations

from unittest.mock import MagicMock

from arbitration.api_client import MultiModelClient
from providers.model_provider import ModelResponse
from providers.registry import ProviderRegistry


def test_multi_model_client_delegates_to_selected_provider() -> None:
    provider = MagicMock()
    provider.generate.return_value = ModelResponse(
        provider="test",
        model="gemini-test",
        text="hello",
        input_tokens=3,
        output_tokens=2,
    )
    registry = ProviderRegistry({"anthropic": MagicMock(), "google": provider})

    response = MultiModelClient(registry=registry).call_model_response(
        model="gemini-test",
        prompt="hello",
    )

    assert response.text == "hello"
    provider.generate.assert_called_once()


def test_string_api_remains_backward_compatible() -> None:
    provider = MagicMock()
    provider.generate.return_value = ModelResponse(
        provider="test",
        model="claude-test",
        text="hello",
    )
    registry = ProviderRegistry({"anthropic": provider, "google": MagicMock()})

    assert MultiModelClient(registry=registry).call_model("claude-test", "hello") == "hello"


def test_short_anthropic_alias_is_canonicalized() -> None:
    provider = MagicMock()
    provider.generate.return_value = ModelResponse(
        provider="test",
        model="claude-sonnet-4-5",
        text="hello",
    )
    registry = ProviderRegistry({"anthropic": provider, "google": MagicMock()})

    MultiModelClient(registry=registry).call_model("sonnet", "hello")

    request = provider.generate.call_args.args[0]
    assert request.model == "claude-sonnet-4-5"


def test_short_anthropic_alias_can_be_overridden() -> None:
    provider = MagicMock()
    provider.generate.return_value = ModelResponse(
        provider="test",
        model="custom-sonnet",
        text="hello",
    )
    registry = ProviderRegistry({"anthropic": provider, "google": MagicMock()})

    import os

    previous = os.environ.get("CLAUDE_SONNET_MODEL")
    os.environ["CLAUDE_SONNET_MODEL"] = "custom-sonnet"
    try:
        MultiModelClient(registry=registry).call_model("sonnet", "hello")
    finally:
        if previous is None:
            os.environ.pop("CLAUDE_SONNET_MODEL", None)
        else:
            os.environ["CLAUDE_SONNET_MODEL"] = previous

    assert provider.generate.call_args.args[0].model == "custom-sonnet"
