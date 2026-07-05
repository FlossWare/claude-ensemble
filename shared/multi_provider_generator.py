#!/usr/bin/env python3
"""
Proxy-based LLM Generator
Uses the unified API proxy at aio-01:8000 with 363 models and automatic failover
"""

import requests
from typing import Optional

class ProxyGenerator:
    """Generate completions using the unified API proxy"""

    def __init__(self):
        self.proxy_url = 'http://aio-01:8000/v1/chat/completions'
        self.request_count = 0

        print(f"✅ Proxy generator initialized (aio-01:8000)")
        print(f"   363 models across 9 providers with auto-failover")

    def generate(self, prompt: str, max_tokens: int = 512, model: str = 'llama-3.3-70b-versatile') -> Optional[str]:
        """
        Generate completion using proxy

        Args:
            prompt: The prompt to complete
            max_tokens: Maximum tokens to generate
            model: Model to use (default: llama-3.3-70b-versatile from Groq - FREE)
        """

        try:
            response = requests.post(
                self.proxy_url,
                headers={'Content-Type': 'application/json'},
                json={
                    'model': model,  # Use specific free model
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            self.request_count += 1

            # Extract response
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']

            return None

        except Exception as e:
            error_msg = str(e)

            # Log error but don't crash
            if '503' in error_msg:
                print(f"  ⚠️  Proxy: All providers temporarily unavailable")
            elif '429' in error_msg:
                print(f"  ⚠️  Proxy: Rate limit reached")
            else:
                print(f"  ⚠️  Proxy error: {error_msg[:100]}")

            return None

    def get_stats(self):
        """Get usage statistics"""
        return {
            'total_requests': self.request_count
        }


# Backwards compatibility with MultiProviderGenerator
class MultiProviderGenerator(ProxyGenerator):
    """Alias for backwards compatibility"""
    pass
