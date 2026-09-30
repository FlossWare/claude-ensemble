#!/usr/bin/env python3
"""
Use gcloud token to authenticate with Anthropic SDK
"""

import subprocess
import logging
import os

logger = logging.getLogger(__name__)


class GcloudTokenClient:
    """Uses gcloud auth token to call Claude via Vertex AI"""

    def __init__(self):
        """Get token from gcloud"""
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get gcloud token: {result.stderr}")

        self.token = result.stdout.strip()
        self.project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")

        logger.info(f"✓ Got gcloud access token for project {self.project_id}")

    def call_model(self, model: str, prompt: str) -> tuple:
        """Call Claude via Anthropic SDK with gcloud token"""
        try:
            from anthropic import Anthropic

            # Use token with API key parameter
            client = Anthropic(
                api_key=self.token,
                base_url=f"https://generativelanguage.googleapis.com/v1beta/openai/",
            )

            response = client.messages.create(
                model=model or "claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            tokens_used = (
                response.usage.input_tokens + response.usage.output_tokens
            )

            # Cost: Sonnet $3/MTok input, $15/MTok output
            input_cost = response.usage.input_tokens / 1_000_000 * 3
            output_cost = response.usage.output_tokens / 1_000_000 * 15
            cost = input_cost + output_cost

            response_text = response.content[0].text

            logger.info(
                f"✓ Claude via gcloud token: {tokens_used} tokens, ${cost:.6f}"
            )
            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise RuntimeError(f"Cannot execute: {e}") from e
