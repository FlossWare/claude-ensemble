#!/usr/bin/env python3
"""
Vertex AI client for calling Claude via Google Cloud
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


class VertexAIClient:
    """Client for Vertex AI Claude API"""

    def __init__(self):
        """Initialize Vertex AI client"""
        self.project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
        if not self.project_id:
            raise RuntimeError("ANTHROPIC_VERTEX_PROJECT_ID not set")

    def call_model(self, model: str, prompt: str) -> tuple:
        """Call Claude via Vertex AI and return (response_text, tokens_used, cost)"""
        try:
            import anthropic

            client = anthropic.Anthropic(
                api_key="",  # Vertex uses implicit authentication
            )

            response = client.messages.create(
                model=model or "claude-opus-5-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            tokens_used = (
                response.usage.input_tokens + response.usage.output_tokens
            )
            # Pricing: Opus-5.5 at $3/MTok input, $15/MTok output
            input_cost = response.usage.input_tokens / 1_000_000 * 3
            output_cost = response.usage.output_tokens / 1_000_000 * 15
            cost = input_cost + output_cost

            response_text = response.content[0].text

            logger.info(
                f"Vertex API call to {model}: {tokens_used} tokens, ${cost:.4f}"
            )
            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"Vertex API call failed: {e}")
            raise RuntimeError(f"Vertex AI execution failed: {e}") from e
