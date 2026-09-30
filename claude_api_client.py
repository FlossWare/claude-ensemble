#!/usr/bin/env python3
"""
Claude API Client - uses Claude Code's direct Claude access
"""

import json
import logging

logger = logging.getLogger(__name__)


class ClaudeCodeAPIClient:
    """API client that works within Claude Code environment"""

    def __init__(self):
        """Initialize - uses Claude Code's built-in Claude access"""
        # This would be called from within Claude Code context
        # For standalone testing, falls back to error
        pass

    def call_model(self, model: str, prompt: str) -> tuple:
        """
        Call Claude API and return (response_text, tokens_used, cost)

        In Claude Code environment, this would use the built-in access.
        For testing outside Claude Code, returns synthetic data but with REAL structure.
        """
        try:
            # Try to import anthropic (available in Claude Code)
            from anthropic import Anthropic

            client = Anthropic()

            # Call the API
            response = client.messages.create(
                model=model or "claude-opus-5-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract metrics
            tokens_used = (
                response.usage.input_tokens + response.usage.output_tokens
            )
            # Pricing: Opus-5.5 at $3/MTok input, $15/MTok output
            input_cost = response.usage.input_tokens / 1_000_000 * 3
            output_cost = response.usage.output_tokens / 1_000_000 * 15
            cost = input_cost + output_cost

            response_text = response.content[0].text

            logger.info(
                f"API call to {model}: {tokens_used} tokens, ${cost:.4f}"
            )
            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise RuntimeError(
                f"Cannot execute solve/review without real API: {e}"
            ) from e
