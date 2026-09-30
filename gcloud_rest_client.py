#!/usr/bin/env python3
"""
Call Claude via Vertex AI REST API with gcloud token
"""

import subprocess
import json
import logging
import os

logger = logging.getLogger(__name__)


class GcloudRestClient:
    """Uses gcloud token to call Claude via Vertex AI REST API"""

    def __init__(self):
        """Initialize with gcloud credentials"""
        self.project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
        if not self.project_id:
            raise RuntimeError("ANTHROPIC_VERTEX_PROJECT_ID not set")

        # Get token
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get token: {result.stderr}")

        self.token = result.stdout.strip()
        logger.info(f"✓ Got gcloud token for {self.project_id}")

    def call_model(self, model: str, prompt: str) -> tuple:
        """Call Claude via Vertex AI REST API"""
        try:
            model = model or "claude-3-5-sonnet@20241022"

            # Build API endpoint
            endpoint = (
                f"https://us-central1-aiplatform.googleapis.com/v1/projects/"
                f"{self.project_id}/locations/us-central1/endpoints/openapi/"
                f"models/{model}:rawPredict"
            )

            # Build request
            request_data = {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }

            # Use curl to make the request
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(request_data, f)
                request_file = f.name

            try:
                cmd = [
                    "curl",
                    "-s",
                    "-X", "POST",
                    f"-H", f"Authorization: Bearer {self.token}",
                    f"-H", "Content-Type: application/json",
                    "-d", f"@{request_file}",
                    endpoint
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    raise RuntimeError(f"curl failed: {result.stderr}")

                # Parse response
                response_data = json.loads(result.stdout)

                # Extract text
                response_text = response_data.get("content", [{}])[0].get("text", "")
                if not response_text:
                    # Try alternate response format
                    response_text = str(response_data)

                # Estimate tokens
                tokens_used = len(prompt.split()) + len(response_text.split())

                # Cost estimate
                cost = (tokens_used / 1000) * 0.015

                logger.info(
                    f"✓ Claude ({model}): {tokens_used} tokens, ${cost:.6f}"
                )

                return response_text, tokens_used, cost

            finally:
                os.unlink(request_file)

        except Exception as e:
            logger.error(f"REST API call failed: {e}")
            raise RuntimeError(f"Cannot execute: {e}") from e
