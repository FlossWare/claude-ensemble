#!/usr/bin/env python3
"""
Multi-Provider Model Router
Routes tasks to the best model across OpenAI, Anthropic, Mistral, Google, Cloudflare
"""

import os
import json
import random
import requests
from typing import List, Dict, Optional

# Load model config
CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    '../config/multi-provider-models.json'
)

with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

class MultiProviderRouter:
    """Route tasks to optimal model across all providers"""

    def __init__(self):
        self.providers = CONFIG['providers']
        self.routing = CONFIG['routing_strategy']

    def get_best_model(self, task_type: str = 'balanced', budget: str = 'balanced') -> Dict:
        """
        Get best model for task type and budget

        Args:
            task_type: premium, balanced, cost_effective, free, code, reasoning
            budget: premium, balanced, cost_effective, free

        Returns:
            {
                'provider': 'openai',
                'model': 'gpt-4o-mini',
                'endpoint': 'https://api.openai.com/v1/chat/completions',
                'api_key': '***',
                'cost_per_1m_input': 0.15
            }
        """

        # Get candidate models for task type
        candidates = self.routing.get(task_type, self.routing['balanced'])

        # Filter by budget if specified
        if budget != task_type:
            budget_models = self.routing.get(budget, [])
            # Prefer models in both lists, fallback to budget
            overlap = [m for m in candidates if m in budget_models]
            candidates = overlap if overlap else budget_models

        # Pick random model for load balancing
        model_id = random.choice(candidates)

        # Find provider and model details
        for provider_name, provider_config in self.providers.items():
            models = provider_config.get('models', {})
            if model_id in models:
                model_config = models[model_id]

                # Get API key
                key_env = provider_config.get('key_env')
                api_key = os.getenv(key_env) if key_env else None

                # Build endpoint
                base_url = provider_config.get('base_url', '')
                endpoint = f"{base_url}/chat/completions"

                return {
                    'provider': provider_name,
                    'model': model_id,
                    'model_config': model_config,
                    'endpoint': endpoint,
                    'api_key': api_key,
                    'cost_per_1m_input': model_config.get('cost_per_1m_input', 0),
                    'cost_per_1m_output': model_config.get('cost_per_1m_output', 0)
                }

        raise ValueError(f"Model {model_id} not found in any provider")

    def call_model(self, model_info: Dict, messages: List[Dict],
                   max_tokens: int = 1000, temperature: float = 0.7) -> Dict:
        """
        Call model via unified interface

        Args:
            model_info: From get_best_model()
            messages: [{"role": "user", "content": "..."}]
            max_tokens: Max output tokens
            temperature: 0-1

        Returns:
            {
                'response': 'model output',
                'tokens_in': 100,
                'tokens_out': 50,
                'cost': 0.001,
                'provider': 'openai',
                'model': 'gpt-4o-mini'
            }
        """

        provider = model_info['provider']

        # Anthropic uses different format
        if provider == 'anthropic':
            return self._call_anthropic(model_info, messages, max_tokens, temperature)

        # OpenAI-compatible format (OpenAI, Mistral, etc.)
        return self._call_openai_compatible(model_info, messages, max_tokens, temperature)

    def _call_openai_compatible(self, model_info, messages, max_tokens, temperature):
        """Call OpenAI-compatible API (OpenAI, Mistral, Cloudflare)"""

        headers = {
            'Authorization': f"Bearer {model_info['api_key']}",
            'Content-Type': 'application/json'
        }

        payload = {
            'model': model_info['model'],
            'messages': messages,
            'max_tokens': max_tokens,
            'temperature': temperature
        }

        response = requests.post(
            model_info['endpoint'],
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text}")

        data = response.json()

        # Extract response
        response_text = data['choices'][0]['message']['content']
        tokens_in = data['usage']['prompt_tokens']
        tokens_out = data['usage']['completion_tokens']

        # Calculate cost
        cost = (
            (tokens_in / 1_000_000) * model_info['cost_per_1m_input'] +
            (tokens_out / 1_000_000) * model_info['cost_per_1m_output']
        )

        return {
            'response': response_text,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'cost': cost,
            'provider': model_info['provider'],
            'model': model_info['model']
        }

    def _call_anthropic(self, model_info, messages, max_tokens, temperature):
        """Call Anthropic API (different format)"""

        # Convert messages format
        system_msg = None
        converted_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_msg = msg['content']
            else:
                converted_messages.append(msg)

        headers = {
            'x-api-key': model_info['api_key'],
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': model_info['model'],
            'messages': converted_messages,
            'max_tokens': max_tokens,
            'temperature': temperature
        }

        if system_msg:
            payload['system'] = system_msg

        response = requests.post(
            f"{model_info['endpoint'].replace('/chat/completions', '/messages')}",
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code != 200:
            raise Exception(f"Anthropic API error {response.status_code}: {response.text}")

        data = response.json()

        response_text = data['content'][0]['text']
        tokens_in = data['usage']['input_tokens']
        tokens_out = data['usage']['output_tokens']

        cost = (
            (tokens_in / 1_000_000) * model_info['cost_per_1m_input'] +
            (tokens_out / 1_000_000) * model_info['cost_per_1m_output']
        )

        return {
            'response': response_text,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'cost': cost,
            'provider': model_info['provider'],
            'model': model_info['model']
        }

    def get_all_models(self, tier: Optional[str] = None) -> List[Dict]:
        """List all available models, optionally filtered by tier"""

        models = []

        for provider_name, provider_config in self.providers.items():
            for model_id, model_config in provider_config.get('models', {}).items():
                if tier and model_config.get('tier') != tier:
                    continue

                models.append({
                    'provider': provider_name,
                    'model': model_id,
                    'tier': model_config.get('tier'),
                    'cost_per_1m_input': model_config.get('cost_per_1m_input', 0),
                    'context': model_config.get('context'),
                    'use_cases': model_config.get('use_cases', [])
                })

        return models


# CLI usage
if __name__ == '__main__':
    import sys

    router = MultiProviderRouter()

    if len(sys.argv) > 1 and sys.argv[1] == 'list':
        # List all models
        tier = sys.argv[2] if len(sys.argv) > 2 else None
        models = router.get_all_models(tier=tier)

        print(f"\nAvailable Models ({len(models)} total):\n")
        print(f"{'Provider':<12} {'Model':<40} {'Tier':<15} {'$/1M in':<10}")
        print("-" * 85)

        for m in sorted(models, key=lambda x: x['cost_per_1m_input']):
            print(f"{m['provider']:<12} {m['model']:<40} {m['tier']:<15} ${m['cost_per_1m_input']:<9.2f}")

    elif len(sys.argv) > 1 and sys.argv[1] == 'test':
        # Test a query
        task_type = sys.argv[2] if len(sys.argv) > 2 else 'balanced'
        query = sys.argv[3] if len(sys.argv) > 3 else 'What is 2+2?'

        print(f"\nRouting task_type='{task_type}' to best model...")

        model_info = router.get_best_model(task_type=task_type)
        print(f"Selected: {model_info['provider']} / {model_info['model']}")
        print(f"Cost: ${model_info['cost_per_1m_input']:.2f}/1M input")

        messages = [{'role': 'user', 'content': query}]

        try:
            result = router.call_model(model_info, messages, max_tokens=100)
            print(f"\nResponse: {result['response']}")
            print(f"Tokens: {result['tokens_in']} in, {result['tokens_out']} out")
            print(f"Cost: ${result['cost']:.4f}")
        except Exception as e:
            print(f"\nError: {e}")

    else:
        print("Usage:")
        print("  python3 multi_provider_router.py list [tier]")
        print("  python3 multi_provider_router.py test [task_type] [query]")
        print("\nTiers: premium, balanced, cost_effective, free")
        print("Task types: premium, balanced, cost_effective, free, code, reasoning")
