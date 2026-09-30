#!/usr/bin/env python3
"""
Diagnostic Queries — Ad-hoc investigation interface

Run semantic searches and graph queries to answer questions:
- "Why did this review fail?"
- "What's the cost trend over time?"
- "Which models are struggling?"

Simple wrapper around Memory Service (semantic search) + GraphDB (relationships).
"""

import logging
import requests
from typing import Dict, List, Optional, Any
from learning_analytics import calculate_confidence

logger = logging.getLogger(__name__)

ENSEMBLE_SERVER_URL = "http://127.0.0.1:8080"


class DiagnosticQueries:
    """Ad-hoc investigation interface"""

    def __init__(self):
        self.ensemble_server_url = ENSEMBLE_SERVER_URL

    def semantic_search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Semantic search on Memory Service.

        Examples:
          - "expensive code review"
          - "sonnet failed security audit"
          - "low confidence arbitration"
          - "large scope timeout"

        Returns: matching arbitration records with snippets
        """
        try:
            response = requests.post(
                f"{self.ensemble_server_url}/memory/search",
                json={'query': query, 'limit': limit},
                timeout=5.0
            )
            response.raise_for_status()

            results = response.json().get('results', [])
            return {
                'ok': True,
                'error': None,
                'data': {
                    'query': query,
                    'count': len(results),
                    'results': results
                }
            }

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }

    def graph_traversal(self, start_node: str, max_depth: int = 3) -> Dict[str, Any]:
        """Traverse graph from a node.

        Examples:
          - start_node='model:opus' (find all tasks it worked on)
          - start_node='task:code_review' (find all models used)
          - start_node='outcome:xyz' (find related models + tasks)

        Returns: BFS traversal with nodes and edges
        """
        try:
            response = requests.post(
                f"{self.ensemble_server_url}/graph/traverse",
                json={'start': start_node, 'max_depth': max_depth},
                timeout=5.0
            )
            response.raise_for_status()

            data = response.json().get('data', {})
            return {
                'ok': True,
                'error': None,
                'data': {
                    'start': start_node,
                    'nodes_found': len(data.get('nodes', {})),
                    'edges_found': len(data.get('edges', [])),
                    'graph_data': data
                }
            }

        except Exception as e:
            logger.error(f"Error in graph traversal: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }

    def find_model_patterns(self, model: str) -> Dict[str, Any]:
        """Analyze patterns for a specific model.

        Returns:
          - Tasks it's attempted
          - Success/failure rate by task
          - Average cost
          - Trend (improving vs degrading?)
        """
        try:
            results = {}

            # Traverse from model node
            traversal = self.graph_traversal(f'model:{model}', max_depth=2)
            if not traversal.get('ok'):
                return {
                    'ok': False,
                    'error': 'Model not found in graph',
                    'data': None
                }

            # Extract task relationships
            graph_data = traversal.get('data', {})
            graph = graph_data.get('graph_data', {})
            edges = graph.get('edges', [])

            tasks = {}
            for edge in edges:
                if edge.get('relationship') in ['succeeded_on', 'failed_on']:
                    to_id = edge.get('to_id', '')
                    if to_id.startswith('task:'):
                        task = to_id.replace('task:', '')
                        if task not in tasks:
                            tasks[task] = {'succeeded': 0, 'failed': 0}
                        if 'succeeded' in edge.get('relationship'):
                            tasks[task]['succeeded'] += 1
                        else:
                            tasks[task]['failed'] += 1

            # Calculate success rates
            task_stats = {}
            total_attempts = 0
            for task, counts in tasks.items():
                total = counts['succeeded'] + counts['failed']
                success_rate = counts['succeeded'] / total if total > 0 else 0
                total_attempts += total
                task_stats[task] = {
                    'attempts': total,
                    'success_rate': round(success_rate, 2),
                    'failures': counts['failed']
                }

            # Calculate confidence for overall model performance
            conf_result = calculate_confidence(total_attempts)

            return {
                'ok': True,
                'error': None,
                'data': {
                    'model': model,
                    'tasks_attempted': len(task_stats),
                    'task_stats': task_stats,
                    'overall_success_rate': sum(
                        s['success_rate'] for s in task_stats.values()
                    ) / len(task_stats) if task_stats else 0,
                    'confidence': conf_result['confidence'],
                    'confidence_level': conf_result['confidence_level'],
                    'sample_size': conf_result['sample_size'],
                    **(conf_result if 'warning' in conf_result else {})
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing model patterns: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }

    def find_problematic_tasks(self) -> Dict[str, Any]:
        """Find tasks with high failure rates.

        Returns: ranked list of task types with failure patterns
        """
        try:
            # Search for failures in memory service
            response = requests.post(
                f"{self.ensemble_server_url}/memory/search",
                json={'query': 'failed inconclusive low confidence', 'limit': 50},
                timeout=5.0
            )
            response.raise_for_status()

            results = response.json().get('results', [])

            # Aggregate by task type from content
            task_failures = {}
            for result in results:
                content = result.get('content', '')
                # Extract task type from markdown
                for line in content.split('\n'):
                    if '**Type:**' in line:
                        task_type = line.split('**Type:**')[1].strip()
                        task_failures[task_type] = task_failures.get(task_type, 0) + 1

            # Sort by failure count
            ranked = sorted(task_failures.items(), key=lambda x: x[1], reverse=True)

            # Calculate overall confidence based on total failure count
            total_failures = sum(task_failures.values())
            conf_result = calculate_confidence(total_failures)

            return {
                'ok': True,
                'error': None,
                'data': {
                    'problem_tasks': ranked,
                    'highest_risk': ranked[0][0] if ranked else None,
                    'confidence': conf_result['confidence'],
                    'confidence_level': conf_result['confidence_level'],
                    'sample_size': conf_result['sample_size'],
                    **(conf_result if 'warning' in conf_result else {})
                }
            }

        except Exception as e:
            logger.error(f"Error finding problematic tasks: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }

    def cost_outliers(self, percentile: float = 0.9) -> Dict[str, Any]:
        """Find unusually expensive arbitrations.

        Returns: arbitrations in top percentile by cost
        """
        try:
            response = requests.post(
                f"{self.ensemble_server_url}/memory/search",
                json={'query': 'arbitration cost expensive', 'limit': 100},
                timeout=5.0
            )
            response.raise_for_status()

            results = response.json().get('results', [])

            # Extract costs from markdown
            costs = []
            cost_records = []
            for result in results:
                content = result.get('content', '')
                for line in content.split('\n'):
                    if '**Total Cost:**' in line:
                        try:
                            cost_str = line.split('**Total Cost:**')[1].strip().lstrip('$')
                            cost = float(cost_str)
                            costs.append(cost)
                            cost_records.append({'cost': cost, 'record': result})
                        except:
                            pass

            if not costs:
                return {
                    'ok': True,
                    'error': None,
                    'data': {
                        'outliers': [],
                        'percentile': percentile
                    }
                }

            # Find outliers (top percentile) - correct percentile calculation
            sorted_costs = sorted(costs)
            percentile_index = max(0, int(len(sorted_costs) * percentile) - 1)
            threshold = sorted_costs[percentile_index]

            outliers = [r for r in cost_records if r['cost'] >= threshold]
            outliers.sort(key=lambda x: x['cost'], reverse=True)

            # Calculate confidence based on number of costs analyzed
            conf_result = calculate_confidence(len(costs))

            return {
                'ok': True,
                'error': None,
                'data': {
                    'percentile': percentile,
                    'threshold': round(threshold, 4),
                    'outlier_count': len(outliers),
                    'outliers': [{'cost': o['cost'], 'title': o.get('record', {}).get('title', 'unknown')} for o in outliers[:10]],
                    'confidence': conf_result['confidence'],
                    'confidence_level': conf_result['confidence_level'],
                    'sample_size': conf_result['sample_size'],
                    **(conf_result if 'warning' in conf_result else {})
                }
            }

        except Exception as e:
            logger.error(f"Error finding cost outliers: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }

    def trend_analysis(self, task_type: str, metric: str = 'cost') -> Dict[str, Any]:
        """Analyze trends over time.

        metric: 'cost', 'confidence', 'success_rate'

        Returns: trend line (improving vs degrading)
        """
        try:
            response = requests.post(
                f"{self.ensemble_server_url}/memory/search",
                json={'query': f'{task_type} outcome', 'limit': 50},
                timeout=5.0
            )
            response.raise_for_status()

            results = response.json().get('results', [])

            # Extract metric values (simplified: just aggregate)
            values = []
            for result in results:
                content = result.get('content', '')
                if metric == 'cost':
                    for line in content.split('\n'):
                        if '**Total Cost:**' in line:
                            try:
                                cost_str = line.split('**Total Cost:**')[1].strip().lstrip('$')
                                values.append(float(cost_str))
                            except:
                                pass

            if not values:
                return {
                    'ok': True,
                    'error': None,
                    'data': {
                        'status': 'insufficient_data'
                    }
                }

            if len(values) < 2:
                return {
                    'ok': True,
                    'error': None,
                    'data': {
                        'task_type': task_type,
                        'metric': metric,
                        'samples': len(values),
                        'average': values[0] if values else 0,
                        'trend': 'insufficient_data',
                        'note': 'Need at least 2 samples to determine trend'
                    }
                }

            avg = sum(values) / len(values)
            mid_point = len(values) // 2
            first_half = values[:mid_point]
            second_half = values[mid_point:]

            first_half_avg = sum(first_half) / len(first_half) if first_half else avg
            second_half_avg = sum(second_half) / len(second_half) if second_half else avg

            trend = 'improving' if second_half_avg < first_half_avg else \
                   'degrading' if second_half_avg > first_half_avg else 'stable'

            # Calculate confidence based on number of samples
            conf_result = calculate_confidence(len(values))

            return {
                'ok': True,
                'error': None,
                'data': {
                    'task_type': task_type,
                    'metric': metric,
                    'samples': len(values),
                    'average': round(avg, 4),
                    'first_half_avg': round(first_half_avg, 4),
                    'second_half_avg': round(second_half_avg, 4),
                    'trend': trend,
                    'confidence': conf_result['confidence'],
                    'confidence_level': conf_result['confidence_level'],
                    'sample_size': conf_result['sample_size'],
                    **(conf_result if 'warning' in conf_result else {})
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    diag = DiagnosticQueries()

    print("=== Diagnostic Queries ===\n")

    print("1. Semantic search for expensive reviews:")
    results = diag.semantic_search("expensive code review", limit=5)
    print(f"  Found {results.get('count', 0)} results\n")

    print("2. Graph traversal from model:sonnet:")
    trav = diag.graph_traversal('model:sonnet', max_depth=2)
    print(f"  Found {trav.get('nodes_found', 0)} nodes, {trav.get('edges_found', 0)} edges\n")

    print("3. Model patterns for sonnet:")
    patterns = diag.find_model_patterns('sonnet')
    print(f"  {patterns}\n")

    print("4. Problematic tasks:")
    problems = diag.find_problematic_tasks()
    print(f"  {problems}\n")

    print("5. Cost outliers (top 10%):")
    outliers = diag.cost_outliers(percentile=0.9)
    print(f"  {outliers}")
