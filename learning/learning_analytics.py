#!/usr/bin/env python3
"""
Learning Analytics — Query System for Decision Support

Unified interface to query Memory Service, GraphDB, and Thompson
for insights that help make arbitration decisions.

Answers:
- "Which models work best for code reviews?"
- "What's the cost-quality tradeoff for large tasks?"
- "Should we use 2 or 3 phases?"
"""

import logging
import requests
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

ENSEMBLE_SERVER_URL = "http://127.0.0.1:8080"


class LearningAnalytics:
    """Query learning system for insights"""

    def __init__(self):
        self.ensemble_server_url = ENSEMBLE_SERVER_URL

    def best_models_for(self, task_type: str, scope: str = None,
                       limit: int = 5) -> List[Dict[str, Any]]:
        """Find best models for task type (and optionally, scope).

        Returns ranked list with success rates, avg cost, confidence.

        Example:
          best_models_for('code_review', 'small')
          → [
              {'model': 'sonnet', 'success_rate': 0.92, 'avg_cost': 0.15, 'confidence': 0.89},
              {'model': 'opus', 'success_rate': 0.88, 'avg_cost': 0.35, 'confidence': 0.91},
            ]
        """
        try:
            # Query graph: which models succeeded on this task_type?
            response = requests.post(
                f"{self.ensemble_server_url}/graph/query",
                json={
                    'type': 'edges',
                    'from_type': 'model',
                    'to_type': 'task_type',
                    'relationship': 'succeeded_on'
                },
                timeout=5.0
            )
            response.raise_for_status()

            edges = response.json().get('edges', [])

            # Filter and aggregate by model
            model_stats = defaultdict(lambda: {'success': 0, 'total': 0, 'costs': []})

            for edge in edges:
                from_id = edge.get('from_id', '')
                to_id = edge.get('to_id', '')
                cost = edge.get('properties', {}).get('cost', 0.0)

                if from_id.startswith('model:') and to_id == f'task:{task_type}':
                    model = from_id.replace('model:', '')
                    model_stats[model]['success'] += 1
                    model_stats[model]['total'] += 1
                    if cost:
                        model_stats[model]['costs'].append(cost)

            # Also query failures to calculate success rate
            response = requests.post(
                f"{self.ensemble_server_url}/graph/query",
                json={
                    'type': 'edges',
                    'from_type': 'model',
                    'to_type': 'task_type',
                    'relationship': 'failed_on'
                },
                timeout=5.0
            )
            response.raise_for_status()
            edges = response.json().get('edges', [])
            for edge in edges:
                from_id = edge.get('from_id', '')
                to_id = edge.get('to_id', '')
                if from_id.startswith('model:') and to_id == f'task:{task_type}':
                    model = from_id.replace('model:', '')
                    model_stats[model]['total'] += 1

            # Calculate rates and rank
            results = []
            for model, stats in model_stats.items():
                if stats['total'] > 0:
                    success_rate = stats['success'] / stats['total']
                    avg_cost = sum(stats['costs']) / len(stats['costs']) if stats['costs'] else 0.0
                    results.append({
                        'model': model,
                        'success_rate': round(success_rate, 2),
                        'attempts': stats['total'],
                        'avg_cost': round(avg_cost, 4),
                        'confidence': min(1.0, stats['total'] / 10.0)  # Higher with more data
                    })

            # Sort by success rate (descending)
            results.sort(key=lambda x: x['success_rate'], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Error querying best models: {e}")
            return {'ok': False, 'error': str(e), 'data': []}

    def cost_quality_tradeoff(self, task_type: str) -> Dict[str, Any]:
        """Analyze cost vs quality tradeoff for task type.

        Returns: cheap but low-confidence vs expensive but high-confidence models

        Example:
          cost_quality_tradeoff('security_audit')
          → {
              'cheap': {'model': 'haiku', 'avg_cost': 0.05, 'confidence': 0.70},
              'quality': {'model': 'opus', 'avg_cost': 0.45, 'confidence': 0.95},
              'balanced': {'model': 'sonnet', 'avg_cost': 0.15, 'confidence': 0.88}
            }
        """
        try:
            models = self.best_models_for(task_type, limit=10)

            if not models:
                return {'error': f'No data for {task_type}'}

            # Categorize by cost vs confidence
            cheap = min(models, key=lambda x: x['avg_cost'])
            quality = max(models, key=lambda x: x['confidence'])

            # Find balanced
            balanced = min(
                models,
                key=lambda x: abs(x['avg_cost'] - quality['avg_cost'] / 2)
            )

            return {
                'task_type': task_type,
                'cheap': {
                    'model': cheap['model'],
                    'avg_cost': cheap['avg_cost'],
                    'confidence': cheap['confidence']
                },
                'quality': {
                    'model': quality['model'],
                    'avg_cost': quality['avg_cost'],
                    'confidence': quality['confidence']
                },
                'balanced': {
                    'model': balanced['model'],
                    'avg_cost': balanced['avg_cost'],
                    'confidence': balanced['confidence']
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing cost-quality: {e}")
            return {'error': str(e)}

    def failure_analysis(self, task_type: str) -> Dict[str, Any]:
        """Analyze why tasks of this type fail.

        Returns: failure patterns, most common failure modes, affected models

        Example:
          failure_analysis('code_review')
          → {
              'failure_rate': 0.12,
              'total_failures': 3,
              'affected_models': ['haiku', 'flash'],
              'patterns': 'Low confidence on large scopes',
              'recommendation': 'Use Sonnet for large code reviews'
            }
        """
        try:
            # Query outcomes for this task type
            response = requests.post(
                f"{self.ensemble_server_url}/memory/search",
                json={'query': f'{task_type} inconclusive failed', 'limit': 50},
                timeout=5.0
            )
            response.raise_for_status()

            results = response.json().get('results', [])

            if not results:
                return {
                    'task_type': task_type,
                    'failure_rate': 0.0,
                    'finding': 'No failures recorded'
                }

            # Parse outcomes for patterns
            failures = []
            for result in results:
                content = result.get('content', '')
                if 'inconclusive' in content.lower() or 'failed' in content.lower():
                    failures.append(content)

            # Count failures by model using graph query
            # Query graph for failure edges instead of parsing markdown
            try:
                response = requests.post(
                    f"{self.ensemble_server_url}/graph/query",
                    json={
                        'type': 'edges',
                        'from_type': 'model',
                        'to_type': 'task_type',
                        'relationship': 'failed_on'
                    },
                    timeout=5.0
                )
                response.raise_for_status()
                failure_edges = response.json().get('edges', [])

                model_failures = defaultdict(int)
                for edge in failure_edges:
                    from_id = edge.get('from_id', '')
                    if from_id.startswith('model:'):
                        model = from_id.replace('model:', '')
                        model_failures[model] += 1
            except Exception as e:
                logger.warning(f"Could not query graph for failures: {e}")
                model_failures = {}

            return {
                'task_type': task_type,
                'failure_count': len(failures),
                'affected_models': list(model_failures.keys()),
                'confidence': min(1.0, len(failures) / 10.0),
                'recommendation': f'Consider Opus/Sonnet for {task_type} (cheaper models underperform)'
            }

        except Exception as e:
            logger.error(f"Error analyzing failures: {e}")
            return {'error': str(e)}

    def scope_cost_analysis(self) -> Dict[str, Dict[str, Any]]:
        """Analyze cost patterns by scope (small/medium/large).

        Returns: average cost per scope, variance, recommendations

        Example:
          scope_cost_analysis()
          → {
              'small': {'avg_cost': 0.12, 'min': 0.08, 'max': 0.18},
              'medium': {'avg_cost': 0.28, 'min': 0.15, 'max': 0.45},
              'large': {'avg_cost': 0.85, 'min': 0.60, 'max': 1.20}
            }
        """
        try:
            response = requests.post(
                f"{self.ensemble_server_url}/graph/query",
                json={
                    'type': 'edges',
                    'from_type': 'scope',
                    'to_type': 'task_type'
                },
                timeout=5.0
            )
            response.raise_for_status()

            edges = response.json().get('edges', [])

            scope_costs = defaultdict(list)
            for edge in edges:
                scope = edge.get('from_id', '').replace('scope:', '')
                cost = edge.get('properties', {}).get('cost', 0.0)
                if cost:
                    scope_costs[scope].append(cost)

            result = {}
            for scope, costs in scope_costs.items():
                result[scope] = {
                    'avg_cost': round(sum(costs) / len(costs), 4),
                    'min_cost': round(min(costs), 4),
                    'max_cost': round(max(costs), 4),
                    'samples': len(costs)
                }

            return result

        except Exception as e:
            logger.error(f"Error analyzing scope costs: {e}")
            return {'error': str(e)}

    def model_compatibility(self, model1: str, model2: str,
                          task_type: str = None) -> Dict[str, Any]:
        """Analyze if two models work well together.

        Returns: shared successes, complementary strengths, compatibility score

        Example:
          model_compatibility('sonnet', 'opus', 'security_audit')
          → {
              'models': ['sonnet', 'opus'],
              'task_type': 'security_audit',
              'shared_success_rate': 0.88,
              'compatibility': 0.92
            }
        """
        try:
            # Query graph for both models' success patterns
            response = requests.post(
                f"{self.ensemble_server_url}/graph/traverse",
                json={'start': f'model:{model1}', 'max_depth': 2},
                timeout=5.0
            )
            response.raise_for_status()
            model1_graph = response.json().get('data', {})

            response = requests.post(
                f"{self.ensemble_server_url}/graph/traverse",
                json={'start': f'model:{model2}', 'max_depth': 2},
                timeout=5.0
            )
            response.raise_for_status()
            model2_graph = response.json().get('data', {})

            # Find shared success tasks
            model1_tasks = set(n.replace('task:', '') for n in model1_graph.get('nodes', {}).keys() if n.startswith('task:'))
            model2_tasks = set(n.replace('task:', '') for n in model2_graph.get('nodes', {}).keys() if n.startswith('task:'))
            shared_tasks = model1_tasks & model2_tasks

            compatibility = len(shared_tasks) / max(len(model1_tasks | model2_tasks), 1)

            return {
                'model1': model1,
                'model2': model2,
                'shared_success_tasks': list(shared_tasks),
                'compatibility_score': round(compatibility, 2),
                'recommendation': 'Good pair' if compatibility > 0.7 else 'Consider different models'
            }

        except Exception as e:
            logger.error(f"Error analyzing model compatibility: {e}")
            return {'error': str(e)}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    analytics = LearningAnalytics()

    print("=== Learning Analytics ===\n")

    print("1. Best models for code_review:")
    models = analytics.best_models_for('code_review')
    for m in models:
        print(f"  {m}")

    print("\n2. Cost-quality tradeoff for security_audit:")
    tradeoff = analytics.cost_quality_tradeoff('security_audit')
    print(f"  {tradeoff}")

    print("\n3. Failure analysis:")
    failures = analytics.failure_analysis('code_review')
    print(f"  {failures}")

    print("\n4. Scope cost analysis:")
    scope_costs = analytics.scope_cost_analysis()
    print(f"  {scope_costs}")

    print("\n5. Model compatibility:")
    compat = analytics.model_compatibility('sonnet', 'opus', 'code_review')
    print(f"  {compat}")
