#!/usr/bin/env python3
"""
Vertex AI authenticated client using gcloud credentials
"""

import logging
import os

logger = logging.getLogger(__name__)


class VertexAuthenticatedClient:
    """Uses gcloud authenticated credentials for Vertex AI"""

    def __init__(self):
        """Initialize with gcloud authentication"""
        self.project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
        if not self.project_id:
            raise RuntimeError("ANTHROPIC_VERTEX_PROJECT_ID not set")

        # Import here to use gcloud credentials
        from google.auth import default
        from google.auth.transport.requests import Request

        # Get credentials from gcloud auth
        self.credentials, _ = default()

        logger.info(f"Authenticated with Vertex AI project: {self.project_id}")

    def call_model(self, model: str, prompt: str) -> tuple:
        """Call Claude via Vertex AI with proper authentication"""
        try:
            from anthropic import Anthropic

            # Create client with gcloud credentials
            client = Anthropic(
                api_key="",  # Vertex uses gcloud auth, not API key
                default_headers={
                    "x-goog-user-project": os.getenv("ANTHROPIC_VERTEX_PROJECT_ID"),
                }
            )

            response = client.messages.create(
                model=model or "claude-opus-5-5",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            tokens_used = (
                response.usage.input_tokens + response.usage.output_tokens
            )

            # Cost: Opus-5.5 $3/MTok input, $15/MTok output
            input_cost = response.usage.input_tokens / 1_000_000 * 3
            output_cost = response.usage.output_tokens / 1_000_000 * 15
            cost = input_cost + output_cost

            response_text = response.content[0].text

            logger.info(
                f"✓ Vertex AI ({model}): {tokens_used} tokens, ${cost:.6f}"
            )
            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"Vertex AI call failed: {e}")
            raise RuntimeError(f"Vertex AI execution failed: {e}") from e
