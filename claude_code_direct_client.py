#!/usr/bin/env python3
"""
Direct Claude access via Claude Code

Since this code runs WITHIN Claude Code, we have direct access to Claude.
Just invoke Claude and it will respond.
"""

import logging
import json
import sys

logger = logging.getLogger(__name__)


class ClaudeCodeDirectClient:
    """Direct Claude API access from within Claude Code"""

    def __init__(self):
        """Initialize - we're already in Claude Code"""
        logger.info("✓ Using direct Claude Code access")

    def call_model(self, model: str, prompt: str) -> tuple:
        """
        Call Claude directly

        Since this runs in Claude Code, we communicate back to the
        Claude Code environment which handles the API call for us.
        """
        try:
            # We're in Claude Code - write to stdout/stderr for Claude Code to intercept
            import subprocess

            # Use claude CLI directly since we're in Claude Code environment
            result = subprocess.run(
                ["claude", "ask", prompt],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                raise RuntimeError(f"Claude ask failed: {result.stderr}")

            response_text = result.stdout.strip()

            # Estimate tokens (rough approximation)
            tokens_used = len(prompt.split()) + len(response_text.split())
            cost = (tokens_used / 1000) * 0.015

            logger.info(
                f"✓ Claude direct: {tokens_used} tokens, ${cost:.6f}"
            )

            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"Claude direct call failed: {e}")
            raise RuntimeError(f"Cannot execute: {e}") from e
