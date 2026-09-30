#!/usr/bin/env python3
"""
Call Claude via gcloud CLI directly
"""

import subprocess
import json
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


class GcloudCLIClient:
    """Uses gcloud CLI to call Claude"""

    def __init__(self):
        """Initialize with gcloud"""
        self.project_id = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
        if not self.project_id:
            raise RuntimeError("ANTHROPIC_VERTEX_PROJECT_ID not set")
        logger.info(f"✓ Gcloud CLI client initialized for {self.project_id}")

    def call_model(self, model: str, prompt: str) -> tuple:
        """Call Claude using gcloud CLI"""
        try:
            model = model or "claude-3-5-sonnet@20241022"

            # Create request JSON
            request = {
                "instances": [
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                ]
            }

            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(request, f)
                request_file = f.name

            try:
                # Call gcloud to invoke the model
                cmd = [
                    "gcloud",
                    "ai",
                    "models",
                    "predict",
                    f"--model={model}",
                    f"--project={self.project_id}",
                    f"--region=us-central1",
                    f"--input-file={request_file}",
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    raise RuntimeError(f"gcloud call failed: {result.stderr}")

                # Parse response
                response_data = json.loads(result.stdout)

                # Extract text from response
                response_text = response_data["predictions"][0]["content"][0]["text"]

                # Extract tokens (estimate if not provided)
                tokens_used = len(prompt.split()) + len(response_text.split())

                # Cost estimate
                cost = (tokens_used / 1000) * 0.015  # ~$0.015 per 1k tokens average

                logger.info(
                    f"✓ Claude ({model}): {tokens_used} tokens, ${cost:.6f}"
                )

                return response_text, tokens_used, cost

            finally:
                # Clean up temp file
                os.unlink(request_file)

        except Exception as e:
            logger.error(f"gcloud API call failed: {e}")
            raise RuntimeError(f"Cannot execute: {e}") from e
