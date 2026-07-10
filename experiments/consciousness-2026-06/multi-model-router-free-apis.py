#!/usr/bin/env python3
"""
Multi-Model Router with Free API Support
Integrates free APIs (Groq, DeepSeek, Cerebras, OpenRouter) for worker nodes
Routes based on: node type, task complexity, cost constraints
"""

import os
import json
import random
from pathlib import Path

class MultiModelRouterFreeAPIs:
    def __init__(self):
        # Load fleet API policy
        policy_path = Path.home() / '.claude' / 'lib' / 'fleet-api-policy.json'
        with open(policy_path) as f:
            self.policy = json.load(f)

        # Current node (detect from hostname)
        self.current_node = os.uname().nodename

        # Free API models available
        self.free_api_models = {
            'groq': {
                'llama-3.3-70b-versatile': {
                    'cost': 0.0,
                    'speed': 'fast',
                    'quality': 'high',
                    'rate_limit': '30/min',
                    'params': '70B'
                },
                'llama-3.1-8b-instant': {
                    'cost': 0.0,
                    'speed': 'very_fast',
                    'quality': 'medium',
                    'rate_limit': '30/min',
                    'params': '8B'
                },
                'mixtral-8x7b-32768': {
                    'cost': 0.0,
                    'speed': 'fast',
                    'quality': 'high',
                    'rate_limit': '30/min',
                    'params': '47B'
                }
            },
            'deepseek': {
                'deepseek-chat': {
                    'cost': 0.00014,  # $0.14/1M tokens (very cheap)
                    'speed': 'medium',
                    'quality': 'high',
                    'rate_limit': 'generous',
                    'params': '236B'
                }
            },
            'cerebras': {
                'llama-3.1-70b': {
                    'cost': 0.0,
                    'speed': 'very_fast',
                    'quality': 'high',
                    'rate_limit': 'generous',
                    'params': '70B'
                }
            },
            'openrouter': {
                'meta-llama/llama-3.3-70b-instruct:free': {
                    'cost': 0.0,
                    'speed': 'medium',
                    'quality': 'high',
                    'rate_limit': 'varies',
                    'params': '70B'
                },
                'google/gemini-2.0-flash-exp:free': {
                    'cost': 0.0,
                    'speed': 'fast',
                    'quality': 'high',
                    'rate_limit': 'varies',
                    'params': 'unknown'
                }
            }
        }

        # Paid API models (laptop-01 only)
        self.paid_api_models = {
            'anthropic': {
                'claude-opus-4': {'cost': 0.015, 'quality': 'very_high', 'speed': 'slow'},
                'claude-sonnet-4.5': {'cost': 0.003, 'quality': 'high', 'speed': 'medium'},
                'claude-haiku-4': {'cost': 0.0008, 'quality': 'medium', 'speed': 'fast'}
            },
            'openai': {
                'gpt-4o': {'cost': 0.0025, 'quality': 'high', 'speed': 'medium'},
                'gpt-3.5-turbo': {'cost': 0.0005, 'quality': 'medium', 'speed': 'fast'}
            }
        }

        # Local Ollama models (all nodes)
        self.local_models = {
            'mistral:latest': {'cost': 0.0, 'quality': 'medium', 'speed': 'slow', 'params': '7B'},
            'gemma2:2b': {'cost': 0.0, 'quality': 'low', 'speed': 'medium', 'params': '2B'},
            'phi3.5:latest': {'cost': 0.0, 'quality': 'medium', 'speed': 'medium', 'params': '3.8B'}
        }

    def can_use_paid_apis(self):
        """Check if current node can use paid APIs"""
        return self.current_node == 'laptop-01'

    def route(self, task_type='general', quality_requirement='medium', speed_requirement='medium', budget_constraint=None):
        """
        Route to best model based on requirements

        Args:
            task_type: 'code', 'research', 'general', 'simple'
            quality_requirement: 'low', 'medium', 'high', 'very_high'
            speed_requirement: 'slow', 'medium', 'fast', 'very_fast'
            budget_constraint: 'free', 'cheap', None

        Returns:
            dict: {provider, model, api_key_env_var, cost}
        """

        # Build candidate pool based on node capabilities
        candidates = []

        # Always available: local models
        for model, spec in self.local_models.items():
            candidates.append({
                'provider': 'ollama',
                'model': model,
                'api_key_env_var': None,
                'cost': 0.0,
                'quality': spec['quality'],
                'speed': spec['speed'],
                'source': 'local'
            })

        # Free APIs (all nodes can use these)
        if budget_constraint in ['free', 'cheap', None]:
            # Groq (fast, free)
            if os.getenv('GROQ_API_KEY'):
                for model, spec in self.free_api_models['groq'].items():
                    candidates.append({
                        'provider': 'groq',
                        'model': model,
                        'api_key_env_var': 'GROQ_API_KEY',
                        'cost': 0.0,
                        'quality': spec['quality'],
                        'speed': spec['speed'],
                        'source': 'free_api'
                    })

            # DeepSeek (very cheap)
            if os.getenv('DEEPSEEK_API_KEY'):
                for model, spec in self.free_api_models['deepseek'].items():
                    candidates.append({
                        'provider': 'deepseek',
                        'model': model,
                        'api_key_env_var': 'DEEPSEEK_API_KEY',
                        'cost': spec['cost'],
                        'quality': spec['quality'],
                        'speed': spec['speed'],
                        'source': 'free_api'
                    })

            # Cerebras (fast, free)
            if os.getenv('CEREBRAS_API_KEY'):
                for model, spec in self.free_api_models['cerebras'].items():
                    candidates.append({
                        'provider': 'cerebras',
                        'model': model,
                        'api_key_env_var': 'CEREBRAS_API_KEY',
                        'cost': 0.0,
                        'quality': spec['quality'],
                        'speed': spec['speed'],
                        'source': 'free_api'
                    })

            # OpenRouter free models
            if os.getenv('OPENROUTER_API_KEY'):
                for model, spec in self.free_api_models['openrouter'].items():
                    candidates.append({
                        'provider': 'openrouter',
                        'model': model,
                        'api_key_env_var': 'OPENROUTER_API_KEY',
                        'cost': 0.0,
                        'quality': spec['quality'],
                        'speed': spec['speed'],
                        'source': 'free_api'
                    })

        # Paid APIs (laptop-01 only)
        if self.can_use_paid_apis() and budget_constraint != 'free':
            if os.getenv('OPENAI_API_KEY'):
                for model, spec in self.paid_api_models['openai'].items():
                    candidates.append({
                        'provider': 'openai',
                        'model': model,
                        'api_key_env_var': 'OPENAI_API_KEY',
                        'cost': spec['cost'],
                        'quality': spec['quality'],
                        'speed': spec['speed'],
                        'source': 'paid_api'
                    })

        # Filter and score candidates
        quality_scores = {'low': 1, 'medium': 2, 'high': 3, 'very_high': 4}
        speed_scores = {'slow': 1, 'medium': 2, 'fast': 3, 'very_fast': 4}

        scored_candidates = []
        for candidate in candidates:
            # Quality match
            quality_score = quality_scores.get(candidate['quality'], 2)
            quality_target = quality_scores.get(quality_requirement, 2)
            quality_match = 1.0 if quality_score >= quality_target else 0.5

            # Speed match
            speed_score = speed_scores.get(candidate['speed'], 2)
            speed_target = speed_scores.get(speed_requirement, 2)
            speed_match = 1.0 if speed_score >= speed_target else 0.7

            # Cost preference (free > cheap > paid)
            cost_match = 1.0 if candidate['cost'] == 0.0 else 0.8 if candidate['cost'] < 0.001 else 0.5

            # Task-specific bonuses
            task_bonus = 1.0
            if task_type == 'code' and 'deepseek' in candidate['provider']:
                task_bonus = 1.2
            elif task_type == 'simple' and candidate['speed'] in ['fast', 'very_fast']:
                task_bonus = 1.1

            # Composite score
            score = quality_match * speed_match * cost_match * task_bonus

            scored_candidates.append({
                **candidate,
                'score': score
            })

        # Sort by score (descending)
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)

        if not scored_candidates:
            # Fallback to local
            return {
                'provider': 'ollama',
                'model': 'mistral:latest',
                'api_key_env_var': None,
                'cost': 0.0,
                'source': 'local_fallback'
            }

        # Return top choice
        return scored_candidates[0]

    def fallback_chain(self, preferred_model):
        """
        Generate fallback chain if preferred model fails

        Returns list of models to try in order
        """
        chain = []

        # Start with preferred
        chain.append(preferred_model)

        # Add free APIs as fallbacks
        if os.getenv('GROQ_API_KEY'):
            chain.append({
                'provider': 'groq',
                'model': 'llama-3.3-70b-versatile',
                'api_key_env_var': 'GROQ_API_KEY',
                'cost': 0.0
            })

        if os.getenv('CEREBRAS_API_KEY'):
            chain.append({
                'provider': 'cerebras',
                'model': 'llama-3.1-70b',
                'api_key_env_var': 'CEREBRAS_API_KEY',
                'cost': 0.0
            })

        # Always fallback to local
        chain.append({
            'provider': 'ollama',
            'model': 'mistral:latest',
            'api_key_env_var': None,
            'cost': 0.0
        })

        return chain

if __name__ == '__main__':
    router = MultiModelRouterFreeAPIs()

    print(f"Current node: {router.current_node}")
    print(f"Can use paid APIs: {router.can_use_paid_apis()}")
    print()

    # Test routing scenarios
    scenarios = [
        {'task_type': 'simple', 'quality_requirement': 'medium', 'speed_requirement': 'fast', 'budget_constraint': 'free'},
        {'task_type': 'code', 'quality_requirement': 'high', 'speed_requirement': 'medium', 'budget_constraint': 'cheap'},
        {'task_type': 'research', 'quality_requirement': 'high', 'speed_requirement': 'medium', 'budget_constraint': None},
        {'task_type': 'general', 'quality_requirement': 'medium', 'speed_requirement': 'very_fast', 'budget_constraint': 'free'}
    ]

    for i, scenario in enumerate(scenarios, 1):
        result = router.route(**scenario)
        print(f"Scenario {i}: {scenario}")
        print(f"  → {result['provider']}/{result['model']} (cost: ${result['cost']}, source: {result['source']}, score: {result.get('score', 'N/A')})")
        print()
