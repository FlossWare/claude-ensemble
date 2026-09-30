#!/usr/bin/env python3
"""
Multi-model client using Claude Code's direct access to multiple AI providers

Can call:
- Claude (via Claude Code)
- Gemini (via Google AI SDK)
- Cursor (via Cursor API)
"""

import logging
import os

logger = logging.getLogger(__name__)


class MultiModelClient:
    """Route to different models based on request"""

    def __init__(self):
        """Initialize all available models"""
        logger.info("✓ Multi-model client initialized (Claude + Gemini)")

    def call_model(self, model: str, prompt: str) -> tuple:
        """Call the appropriate model"""

        if not model:
            model = "claude-opus-5-5"

        # Route based on model name
        if "claude" in model.lower():
            return self._call_claude(model, prompt)
        elif "gemini" in model.lower():
            return self._call_gemini(model, prompt)
        elif "cursor" in model.lower():
            return self._call_cursor(model, prompt)
        else:
            # Default to Claude
            return self._call_claude("claude-opus-5-5", prompt)

    def _call_claude(self, model: str, prompt: str) -> tuple:
        """Call Claude via Anthropic SDK"""
        try:
            from anthropic import Anthropic

            client = Anthropic()

            response = client.messages.create(
                model=model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            tokens_used = (
                response.usage.input_tokens + response.usage.output_tokens
            )
            input_cost = response.usage.input_tokens / 1_000_000 * 3
            output_cost = response.usage.output_tokens / 1_000_000 * 15
            cost = input_cost + output_cost

            response_text = response.content[0].text

            logger.info(
                f"✓ Claude ({model}): {tokens_used} tokens, ${cost:.6f}"
            )
            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"Claude call failed: {e}")
            raise RuntimeError(f"Claude execution failed: {e}") from e

    def _call_gemini(self, model: str, prompt: str) -> tuple:
        """Call Gemini via Google AI SDK"""
        try:
            import google.generativeai as genai

            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise RuntimeError("GOOGLE_API_KEY not set")

            genai.configure(api_key=api_key)

            model_obj = genai.GenerativeModel(model or "gemini-2.5-flash")
            response = model_obj.generate_content(prompt)

            response_text = response.text

            # Estimate tokens
            tokens_used = len(prompt.split()) + len(response_text.split())
            cost = (tokens_used / 1000) * 0.001  # Rough estimate

            logger.info(
                f"✓ Gemini ({model}): {tokens_used} tokens, ${cost:.6f}"
            )
            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"Gemini call failed: {e}")
            raise RuntimeError(f"Gemini execution failed: {e}") from e

    def _call_cursor(self, model: str, prompt: str) -> tuple:
        """Call Cursor API"""
        try:
            # Cursor API via HTTP
            import requests

            api_key = os.getenv("CURSOR_API_KEY")
            if not api_key:
                raise RuntimeError("CURSOR_API_KEY not set")

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "model": model or "cursor-pro",
            }

            response = requests.post(
                "https://api.cursor.sh/v1/messages",
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code != 200:
                raise RuntimeError(f"Cursor API error: {response.text}")

            data = response.json()
            response_text = data["content"][0]["text"]

            tokens_used = len(prompt.split()) + len(response_text.split())
            cost = (tokens_used / 1000) * 0.002

            logger.info(
                f"✓ Cursor ({model}): {tokens_used} tokens, ${cost:.6f}"
            )
            return response_text, tokens_used, cost

        except Exception as e:
            logger.error(f"Cursor call failed: {e}")
            raise RuntimeError(f"Cursor execution failed: {e}") from e
