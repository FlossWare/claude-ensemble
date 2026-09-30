#!/usr/bin/env python3
"""
Claude Code native API client - direct access to Claude models
"""

import logging

logger = logging.getLogger(__name__)


class ClaudeCodeNativeClient:
    """Uses Claude Code's built-in direct Claude access"""

    def __init__(self):
        """Initialize - uses Claude Code's native capability"""
        pass

    def call_model(self, model: str, prompt: str) -> tuple:
        """
        Call Claude via Claude Code's native access
        Returns (response_text, tokens_used, cost_usd)
        """
        try:
            from anthropic import Anthropic

            # Claude Code has direct access - uses environment auth
            client = Anthropic()

            response = client.messages.create(
                model=model or "claude-opus-5-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            tokens_used = (
                response.usage.input_tokens + response.usage.output_tokens
            )

            # Cost calculation: Opus-5.5 pricing
            input_cost = response.usage.input_tokens / 1_000_000 * 3
            output_cost = response.usage.output_tokens / 1_000_000 * 15
            cost = input_cost + output_cost

            response_text = response.content[0].text

            logger.info(
                f"Claude API (via Claude Code): {model} → {tokens_used} tokens, ${cost:.6f}"
            )
            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise RuntimeError(f"Cannot execute without Claude API: {e}") from e
