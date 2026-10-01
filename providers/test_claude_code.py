"""Tests for the Claude Code model provider."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from providers.claude_code import ClaudeCodeProvider
from providers.model_provider import ModelRequest


def _completed(stdout: str, returncode: int = 0, stderr: str = ""):
    return type(
        "Completed",
        (),
        {"stdout": stdout, "stderr": stderr, "returncode": returncode},
    )()


def test_parses_success_and_usage_metadata() -> None:
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "model": "claude-sonnet-test",
        "result": "hello",
        "total_cost_usd": 0.0123,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 25,
            "cache_read_input_tokens": 40,
            "cache_creation_input_tokens": 10,
            "thinking_tokens": 7,
        },
    }

    provider = ClaudeCodeProvider()
    with patch("providers.claude_code.shutil.which", return_value="/usr/bin/claude"), patch(
        "providers.claude_code.subprocess.run",
        return_value=_completed(json.dumps(payload)),
    ) as run:
        response = provider.generate(ModelRequest("hello", model="sonnet"))

    assert response.provider == "claude-code"
    assert response.model == "claude-sonnet-test"
    assert response.text == "hello"
    assert response.input_tokens == 100
    assert response.output_tokens == 25
    assert response.cache_read_tokens == 40
    assert response.cache_creation_tokens == 10
    assert response.thinking_tokens == 7
    assert response.cost_usd == 0.0123
    assert response.raw_metadata == payload

    args = run.call_args.args[0]
    assert args[:3] == ["/usr/bin/claude", "--print", "--output-format=json"]
    assert args[-2:] == ["--model", "sonnet"]
    assert run.call_args.kwargs["input"] == "hello"


def test_parses_model_usage_when_top_level_metadata_is_absent() -> None:
    payload = {
        "result": "hello",
        "modelUsage": {
            "claude-haiku-test": {
                "inputTokens": 11,
                "outputTokens": 5,
                "cacheReadInputTokens": 3,
                "cacheCreationInputTokens": 2,
                "costUSD": 0.001,
            }
        },
    }

    provider = ClaudeCodeProvider()
    with patch("providers.claude_code.shutil.which", return_value="/usr/bin/claude"), patch(
        "providers.claude_code.subprocess.run",
        return_value=_completed(json.dumps(payload)),
    ):
        response = provider.generate(ModelRequest("hello"))

    assert response.model == "claude-haiku-test"
    assert response.input_tokens == 11
    assert response.output_tokens == 5
    assert response.cache_read_tokens == 3
    assert response.cache_creation_tokens == 2
    assert response.cost_usd == 0.001


def test_missing_executable_is_clear() -> None:
    provider = ClaudeCodeProvider()
    with patch("providers.claude_code.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="executable not found"):
            provider.generate(ModelRequest("hello"))


def test_nonzero_exit_preserves_stderr() -> None:
    provider = ClaudeCodeProvider()
    with patch("providers.claude_code.shutil.which", return_value="/usr/bin/claude"), patch(
        "providers.claude_code.subprocess.run",
        return_value=_completed("", returncode=2, stderr="authentication failed"),
    ):
        with pytest.raises(RuntimeError, match="authentication failed"):
            provider.generate(ModelRequest("hello"))


def test_malformed_json_is_rejected() -> None:
    provider = ClaudeCodeProvider()
    with patch("providers.claude_code.shutil.which", return_value="/usr/bin/claude"), patch(
        "providers.claude_code.subprocess.run",
        return_value=_completed("not-json"),
    ):
        with pytest.raises(RuntimeError, match="malformed JSON"):
            provider.generate(ModelRequest("hello"))


def test_timeout_is_reported() -> None:
    provider = ClaudeCodeProvider()
    with patch("providers.claude_code.shutil.which", return_value="/usr/bin/claude"), patch(
        "providers.claude_code.subprocess.run",
        side_effect=__import__("subprocess").TimeoutExpired("claude", 1),
    ):
        with pytest.raises(TimeoutError, match="timed out"):
            provider.generate(ModelRequest("hello"))
