#!/usr/bin/env python3
"""
Multi-Model API Client
Unified interface for Anthropic, Google, Cursor APIs
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class MultiModelClient:
    """Unified client for different model providers"""

    def __init__(self):
        self.anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        self.google_key = os.environ.get('GOOGLE_API_KEY')
        self.cursor_key = os.environ.get('CURSOR_API_KEY')

    def call_model(self, model: str, prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """Call a model and get response"""
        if 'claude' in model.lower():
            return self._call_anthropic(model, prompt, system, temperature, max_tokens)
        elif 'gemini' in model.lower():
            return self._call_google(model, prompt, system, temperature, max_tokens)
        elif 'cursor' in model.lower():
            return self._call_cursor(model, prompt, system, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown model: {model}")

    def _call_anthropic(self, model: str, prompt: str, system: str, temperature: float, max_tokens: int) -> str:
        """Call Anthropic Claude API"""
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=self.anthropic_key)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system if system else "You are a helpful assistant.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def _call_google(self, model: str, prompt: str, system: str, temperature: float, max_tokens: int) -> str:
        """Call Google Gemini API"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.google_key)

            # Build messages for Gemini
            full_prompt = f"{system}\n\n{prompt}" if system else prompt

            response = genai.generate_text(
                model=model,
                prompt=full_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
                top_p=0.95,
            )
            return response.result if response.result else ""
        except Exception as e:
            logger.error(f"Google API error: {e}")
            raise

    def _call_cursor(self, model: str, prompt: str, system: str, temperature: float, max_tokens: int) -> str:
        """Call Cursor API (Claude-compatible)"""
        try:
            from anthropic import Anthropic

            # Cursor uses Claude's API with custom endpoint
            client = Anthropic(
                api_key=self.cursor_key,
                base_url="https://api.cursor.sh/v1"  # Cursor endpoint
            )

            response = client.messages.create(
                model=model or "cursor",
                max_tokens=max_tokens,
                temperature=temperature,
                system=system if system else "You are a helpful assistant.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Cursor API error: {e}")
            raise

    def call_models_parallel(self, models: list[str], prompt: str, system: str = "", temperature: float = 0.7) -> Dict[str, str]:
        """Call multiple models in parallel (returns dict of model -> response)"""
        import concurrent.futures

        results = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = {
                executor.submit(self.call_model, model, prompt, system, temperature): model
                for model in models
            }

            for future in concurrent.futures.as_completed(futures):
                model = futures[future]
                try:
                    results[model] = future.result()
                except Exception as e:
                    logger.error(f"Error calling {model}: {e}")
                    results[model] = f"ERROR: {e}"

        return results
