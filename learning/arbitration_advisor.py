#!/usr/bin/env python3
"""
Arbitration Advisor — Pre-Execution Decision Support

Recommends:
- Which models to use (based on success history)
- How many phases (2 vs 3 based on task complexity)
- Expected cost (estimated from history)
- Risk assessment (likelihood of failure/inconclusive)

Used before running arbitration to make smart choices.
"""

import logging
import math
from typing import Dict, List, Optional, Any
from learning_analytics import LearningAnalytics, calculate_confidence

logger = logging.getLogger(__name__)


class ArbitrationAdvisor:
    """Make recommendations before running arbitration"""

    def __init__(self):
        self.analytics = LearningAnalytics()

    def recommend_models(self, task_type: str, scope: str = None,
                        budget: float = None, count: int = 3) -> Dict[str, Any]:
        """Recommend which models to use as workers.

        Args:
          task_type: 'code_review', 'security_audit', etc.
          scope: 'small', 'medium', 'large' (affects complexity)
          budget: max cost allowed (filters expensive models)
          count: how many models to recommend

        Returns:
          {
            'task_type': 'code_review',
            'scope': 'small',
            'recommended': [
              {'model': 'sonnet', 'success_rate': 0.92, 'reason': 'Best performer'},
              {'model': 'opus', 'success_rate': 0.88, 'reason': 'High confidence'},
              {'model': 'flash', 'success_rate': 0.85, 'reason': 'Cost-efficient'}
            ],
            'estimated_cost': 0.45
          }
        """
        try:
            # Get best models for task type
            result = self.analytics.best_models_for(task_type, limit=count + 2)

            if not result.get('ok') or not result.get('data'):
                logger.warning(f"No historical data for {task_type}")
                return {
                    'ok': False,
                    'error': f'No historical data for {task_type}. Run arbitrations first to build decision support data.',
                    'data': None
                }

            models = result.get('data', [])

            # Filter by budget if provided
            if budget:
                models = [m for m in models if m['avg_cost'] <= budget]
                if not models:
                    logger.warning(f"No models within budget ${budget}")
                    return {
                        'ok': False,
                        'error': f'No models available within ${budget} budget',
                        'data': None
                    }

            # Add reasoning
            for i, model in enumerate(models[:count]):
                if i == 0:
                    model['reason'] = f"Best performer ({model['success_rate']:.0%} success)"
                elif i == 1:
                    model['reason'] = f"High confidence ({model['confidence']:.0%})"
                else:
                    model['reason'] = f"Cost-efficient (${model['avg_cost']:.2f})"

            recommended = models[:count]
            # Cost estimate: average worker cost + arbiter cost (separate calculation)
            worker_avg_cost = sum(m['avg_cost'] for m in recommended) / len(recommended)
            arbiter_cost = 0.08  # Typical arbiter cost (smaller output than workers)
            estimated_cost = worker_avg_cost + arbiter_cost

            # Confidence: based on how much historical data we have
            total_attempts = sum(m.get('attempts', 0) for m in recommended)
            conf_result = calculate_confidence(total_attempts)

            return {
                'ok': True,
                'error': None,
                'data': {
                    'task_type': task_type,
                    'scope': scope,
                    'budget': budget,
                    'recommended': recommended,
                    'estimated_cost': round(estimated_cost, 4),
                    'confidence': conf_result['confidence'],
                    'confidence_level': conf_result['confidence_level'],
                    'sample_size': conf_result['sample_size'],
                    **(conf_result if 'warning' in conf_result else {})
                }
            }

        except Exception as e:
            logger.error(f"Error recommending models: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }

    def recommend_phases(self, task_type: str, scope: str,
                        budget: float = None) -> Dict[str, Any]:
        """Recommend phase count (2 vs 3) based on complexity and cost.

        2 phases: cheaper, faster (good for simple tasks, tight budgets)
        3 phases: more thorough, expensive (good for critical reviews)

        Returns:
          {
            'task_type': 'code_review',
            'scope': 'small',
            'recommendation': '2',
            'reasoning': [
              'Small scope: 2 phases sufficient',
              'Historical data: 2-phase success rate 88%',
              'Cost savings: $0.20 vs $0.35'
            ],
            'estimated_costs': {'2_phases': 0.20, '3_phases': 0.35}
          }
        """
        try:
            reasoning = []
            costs_2phase = 0.0
            costs_3phase = 0.0

            # Get historical costs
            scope_costs_result = self.analytics.scope_cost_analysis()
            scope_costs = scope_costs_result.get('data', {}) if scope_costs_result.get('ok') else {}
            if scope in scope_costs:
                avg_cost = scope_costs[scope]['avg_cost']
                costs_2phase = avg_cost * 0.6  # 2 phases cheaper
                costs_3phase = avg_cost * 1.0  # 3 phases full cost

            # Scope-based recommendation
            if scope == 'small':
                recommendation = '2'
                reasoning.append('Small scope: 2 phases sufficient for confidence')
            elif scope == 'medium':
                recommendation = '2'
                reasoning.append('Medium scope: 2 phases recommended (good balance)')
            else:  # large
                recommendation = '3'
                reasoning.append('Large scope: 3 phases recommended (thorough analysis needed)')

            # Budget-based override
            if budget and costs_3phase > budget:
                recommendation = '2'
                reasoning.append(f'Budget constraint: 3 phases (${costs_3phase:.2f}) exceeds budget (${budget:.2f})')

            # Historical data
            failure_analysis_result = self.analytics.failure_analysis(task_type)
            failure_analysis = failure_analysis_result.get('data', {}) if failure_analysis_result.get('ok') else {}
            if failure_analysis.get('failure_count', 0) > 5:
                recommendation = '3'
                reasoning.append(f"High failure rate detected: recommend 3 phases for higher confidence")

            # Calculate confidence in phase recommendation
            # Use the failure count as sample size for consistency
            failure_count = failure_analysis.get('failure_count', 0)
            conf_result = calculate_confidence(failure_count)

            return {
                'ok': True,
                'error': None,
                'data': {
                    'task_type': task_type,
                    'scope': scope,
                    'recommendation': recommendation,
                    'confidence': conf_result['confidence'],
                    'confidence_level': conf_result['confidence_level'],
                    'sample_size': conf_result['sample_size'],
                    **(conf_result if 'warning' in conf_result else {}),
                    'reasoning': reasoning,
                    'estimated_costs': {
                        '2_phases': round(costs_2phase, 4),
                        '3_phases': round(costs_3phase, 4)
                    }
                }
            }

        except Exception as e:
            logger.error(f"Error recommending phases: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }

    def estimate_cost(self, models: List[str], task_type: str,
                     phases: int = 2) -> Dict[str, Any]:
        """Estimate total cost for given model combination.

        Breaks down by: workers, arbiter, total

        Example:
          estimate_cost(['sonnet', 'opus', 'flash'], 'code_review', phases=2)
          → {
              'task_type': 'code_review',
              'phases': 2,
              'workers': ['sonnet', 'opus', 'flash'],
              'worker_cost_per_phase': 0.20,
              'arbiter_cost_per_phase': 0.08,
              'total_per_phase': 0.28,
              'total_multi_phase': 0.56
            }
        """
        try:
            # Get per-model costs from analytics
            best_models_result = self.analytics.best_models_for(task_type, limit=20)
            best_models = best_models_result.get('data', []) if best_models_result.get('ok') else []
            model_costs = {m['model']: m['avg_cost'] for m in best_models}

            # Estimate worker costs
            worker_costs = []
            for model in models:
                # Look up model cost, default to 0.15 if not found
                cost = model_costs.get(model, 0.15)
                worker_costs.append(cost)

            worker_cost_per_phase = sum(worker_costs) / len(worker_costs) if worker_costs else 0.15
            arbiter_cost_per_phase = 0.08  # Typical arbiter cost (smaller output)
            total_per_phase = worker_cost_per_phase + arbiter_cost_per_phase

            # Calculate confidence based on number of best models found
            conf_result = calculate_confidence(len(best_models))

            return {
                'ok': True,
                'error': None,
                'data': {
                    'task_type': task_type,
                    'phases': phases,
                    'workers': models,
                    'worker_cost_per_phase': round(worker_cost_per_phase, 4),
                    'arbiter_cost_per_phase': round(arbiter_cost_per_phase, 4),
                    'total_per_phase': round(total_per_phase, 4),
                    'total_all_phases': round(total_per_phase * phases, 4),
                    'confidence': conf_result['confidence'],
                    'confidence_level': conf_result['confidence_level'],
                    'sample_size': conf_result['sample_size'],
                    **(conf_result if 'warning' in conf_result else {})
                }
            }

        except Exception as e:
            logger.error(f"Error estimating cost: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }

    def full_recommendation(self, task_type: str, scope: str = 'medium',
                          budget: float = None) -> Dict[str, Any]:
        """Full pre-execution recommendation: models, phases, cost, risk.

        One-stop recommendation for arbitration configuration.
        """
        try:
            # Get all recommendations
            model_rec = self.recommend_models(task_type, scope, budget, count=3)
            phase_rec = self.recommend_phases(task_type, scope, budget)

            if not model_rec.get('ok') or not phase_rec.get('ok'):
                return {
                    'ok': False,
                    'error': 'Could not generate recommendations',
                    'data': {
                        'models_error': model_rec.get('error'),
                        'phases_error': phase_rec.get('error')
                    }
                }

            # Extract recommended models
            model_data = model_rec.get('data', {})
            phase_data = phase_rec.get('data', {})
            recommended_models = [m['model'] for m in model_data.get('recommended', [])]
            phases = int(phase_data.get('recommendation', '2'))

            # Estimate cost
            cost_est = self.estimate_cost(recommended_models, task_type, phases)

            # Assess risk
            failure_analysis_result = self.analytics.failure_analysis(task_type)
            failure_analysis = failure_analysis_result.get('data', {}) if failure_analysis_result.get('ok') else {}
            risk_level = 'low' if failure_analysis.get('failure_count', 0) < 3 else \
                        'medium' if failure_analysis.get('failure_count', 0) < 8 else 'high'

            # Aggregate confidence from all components (use minimum)
            overall_confidence = min(
                model_data.get('confidence', 0.0),
                phase_data.get('confidence', 0.0),
                cost_est.get('data', {}).get('confidence', 0.0)
            )

            # Determine overall confidence level based on aggregated confidence
            if overall_confidence >= 0.8:
                overall_confidence_level = 'high'
            elif overall_confidence >= 0.5:
                overall_confidence_level = 'medium'
            else:
                overall_confidence_level = 'low'

            return {
                'ok': True,
                'error': None,
                'data': {
                    'task_type': task_type,
                    'scope': scope,
                    'budget': budget,
                    'recommendation': {
                        'models': recommended_models,
                        'phases': phases,
                        'estimated_cost': cost_est.get('data', {}).get('total_all_phases', 0.0),
                        'risk_level': risk_level,
                        'confidence': overall_confidence,
                        'confidence_level': overall_confidence_level
                    },
                    'details': {
                        'models': model_rec,
                        'phases': phase_rec,
                        'cost': cost_est,
                        'risks': failure_analysis
                    }
                }
            }

        except Exception as e:
            logger.error(f"Error generating full recommendation: {e}")
            return {
                'ok': False,
                'error': str(e),
                'data': None
            }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    advisor = ArbitrationAdvisor()

    print("=== Arbitration Advisor ===\n")

    print("1. Recommend models for code_review (small scope, $0.50 budget):")
    rec = advisor.recommend_models('code_review', 'small', budget=0.50)
    print(f"  {rec}\n")

    print("2. Recommend phases for code_review (small scope):")
    rec = advisor.recommend_phases('code_review', 'small')
    print(f"  {rec}\n")

    print("3. Estimate cost for ['sonnet', 'opus', 'flash']:")
    rec = advisor.estimate_cost(['sonnet', 'opus', 'flash'], 'code_review', phases=2)
    print(f"  {rec}\n")

    print("4. Full recommendation (code_review, small, $0.50):")
    rec = advisor.full_recommendation('code_review', 'small', budget=0.50)
    print(f"  {rec}")
