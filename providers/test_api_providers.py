"""Unit tests for direct external model providers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from providers.anthropic import AnthropicProvider
from providers.google import GoogleProvider
from providers.http import ProviderHTTPError
from providers.model_provider import ModelRequest
from providers.registry import ProviderRegistry


def test_anthropic_normalizes_response_and_usage() -> None:
    response = {
        "id": "msg_123",
        "model": "claude-test",
        "content": [{"type": "text", "text": "hello"}],
        "usage": {
            "input_tokens": 12,
            "output_tokens": 7,
            "cache_read_input_tokens": 3,
            "cache_creation_input_tokens": 2,
        },
    }
    with patch(
        "providers.anthropic.post_json",
        return_value=(response, {"request-id": "req-1"}),
    ) as post:
        result = AnthropicProvider(api_key="test").generate(
            ModelRequest("hello", model="claude-test", system_prompt="system")
        )

    assert result.provider == "anthropic"
    assert result.text == "hello"
    assert result.input_tokens == 12
    assert result.output_tokens == 7
    assert result.cache_read_tokens == 3
    assert result.cache_creation_tokens == 2
    assert result.request_id == "req-1"
    assert result.latency_ms is not None
    payload = post.call_args.kwargs["payload"]
    assert payload["system"] == "system"
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_anthropic_preserves_prior_messages_and_appends_prompt() -> None:
    response = {
        "model": "claude-test",
        "content": [{"type": "text", "text": "6"}],
    }
    request = ModelRequest(
        "What is 2 + 2 + 0?",
        model="claude-test",
        messages=(
            {"role": "user", "content": "Compute 2 + 2."},
            {"role": "assistant", "content": "4"},
        ),
    )
    with patch(
        "providers.anthropic.post_json",
        return_value=(response, {}),
    ) as post:
        AnthropicProvider(api_key="test").generate(request)

    assert post.call_args.kwargs["payload"]["messages"] == [
        {"role": "user", "content": "Compute 2 + 2."},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "What is 2 + 2 + 0?"},
    ]


def test_google_normalizes_response_and_usage() -> None:
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "hello"}],
                    "role": "model",
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
        },
    }
    with patch("providers.google.post_json", return_value=(response, {})) as post:
        result = GoogleProvider(api_key="test").generate(
            ModelRequest("hello", model="gemini-test")
        )

    assert result.provider == "google"
    assert result.model == "gemini-test"
    assert result.text == "hello"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.latency_ms is not None
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == "test"


def test_google_preserves_prior_messages_and_appends_prompt() -> None:
    response = {
        "candidates": [{"content": {"parts": [{"text": "6"}]}}],
    }
    request = ModelRequest(
        "What is 2 + 2 + 0?",
        model="gemini-test",
        messages=(
            {"role": "user", "content": "Compute 2 + 2."},
            {"role": "assistant", "content": "4"},
        ),
    )
    with patch("providers.google.post_json", return_value=(response, {})) as post:
        GoogleProvider(api_key="test").generate(request)

    assert post.call_args.kwargs["payload"]["contents"] == [
        {"role": "user", "parts": [{"text": "Compute 2 + 2."}]},
        {"role": "model", "parts": [{"text": "4"}]},
        {"role": "user", "parts": [{"text": "What is 2 + 2 + 0?"}]},
    ]


def test_missing_credentials_fail_before_network() -> None:
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(api_key="").generate(ModelRequest("hello"))
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        GoogleProvider(api_key="").generate(ModelRequest("hello"))


def test_provider_http_error_is_preserved() -> None:
    error = ProviderHTTPError("google", 429, "rate limited")
    assert str(error) == "google API request failed with HTTP 429: rate limited"


def test_registry_resolves_without_api_knowledge() -> None:
    anthropic = object()
    google = object()
    registry = ProviderRegistry({"anthropic": anthropic, "google": google})
    assert registry.resolve("claude-sonnet") is anthropic
    assert registry.resolve("gemini-test") is google
    with pytest.raises(ValueError, match="No provider mapping"):
        registry.resolve("unknown-model")


def test_temperature_must_be_between_zero_and_two() -> None:
    with pytest.raises(ValueError, match="between 0 and 2"):
        ModelRequest("hello", temperature=-0.1)
    with pytest.raises(ValueError, match="between 0 and 2"):
        ModelRequest("hello", temperature=2.1)
