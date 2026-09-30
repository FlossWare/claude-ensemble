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
from typing import Dict, List, Optional, Any
from learning_analytics import LearningAnalytics

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
            models = self.analytics.best_models_for(task_type, limit=count + 2)

            if not models:
                logger.warning(f"No historical data for {task_type}, using defaults")
                return {
                    'task_type': task_type,
                    'recommended': [
                        {'model': 'claude-sonnet-5', 'reason': 'Default: balanced cost/quality'},
                        {'model': 'gemini-2.0-flash', 'reason': 'Default: cost-efficient'},
                        {'model': 'claude-opus-5-5', 'reason': 'Default: high quality'}
                    ],
                    'estimated_cost': None,
                    'confidence': 0.0,
                    'note': 'No historical data available'
                }

            # Filter by budget if provided
            if budget:
                models = [m for m in models if m['avg_cost'] <= budget]
                if not models:
                    logger.warning(f"No models within budget ${budget}")
                    return {'error': f'No models available within ${budget} budget'}

            # Add reasoning
            for i, model in enumerate(models[:count]):
                if i == 0:
                    model['reason'] = f"Best performer ({model['success_rate']:.0%} success)"
                elif i == 1:
                    model['reason'] = f"High confidence ({model['confidence']:.0%})"
                else:
                    model['reason'] = f"Cost-efficient (${model['avg_cost']:.2f})"

            recommended = models[:count]
            estimated_cost = sum(m['avg_cost'] for m in recommended) / len(recommended) * 1.5  # Arbiter cost

            return {
                'task_type': task_type,
                'scope': scope,
                'budget': budget,
                'recommended': recommended,
                'estimated_cost': round(estimated_cost, 4),
                'confidence': min(1.0, sum(m.get('attempts', 0) for m in recommended) / 10.0)
            }

        except Exception as e:
            logger.error(f"Error recommending models: {e}")
            return {'error': str(e)}

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
            scope_costs = self.analytics.scope_cost_analysis()
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
            failure_analysis = self.analytics.failure_analysis(task_type)
            if failure_analysis.get('failure_count', 0) > 5:
                recommendation = '3'
                reasoning.append(f"High failure rate detected: recommend 3 phases for higher confidence")

            return {
                'task_type': task_type,
                'scope': scope,
                'recommendation': recommendation,
                'reasoning': reasoning,
                'estimated_costs': {
                    '2_phases': round(costs_2phase, 4),
                    '3_phases': round(costs_3phase, 4)
                }
            }

        except Exception as e:
            logger.error(f"Error recommending phases: {e}")
            return {'error': str(e)}

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
            best_models = self.analytics.best_models_for(task_type, limit=20)
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

            return {
                'task_type': task_type,
                'phases': phases,
                'workers': models,
                'worker_cost_per_phase': round(worker_cost_per_phase, 4),
                'arbiter_cost_per_phase': round(arbiter_cost_per_phase, 4),
                'total_per_phase': round(total_per_phase, 4),
                'total_all_phases': round(total_per_phase * phases, 4),
                'confidence': 0.75 if best_models else 0.4
            }

        except Exception as e:
            logger.error(f"Error estimating cost: {e}")
            return {'error': str(e)}

    def full_recommendation(self, task_type: str, scope: str = 'medium',
                          budget: float = None) -> Dict[str, Any]:
        """Full pre-execution recommendation: models, phases, cost, risk.

        One-stop recommendation for arbitration configuration.
        """
        try:
            # Get all recommendations
            model_rec = self.recommend_models(task_type, scope, budget, count=3)
            phase_rec = self.recommend_phases(task_type, scope, budget)

            if 'error' in model_rec or 'error' in phase_rec:
                return {
                    'error': 'Could not generate recommendations',
                    'models_error': model_rec.get('error'),
                    'phases_error': phase_rec.get('error')
                }

            # Extract recommended models
            recommended_models = [m['model'] for m in model_rec.get('recommended', [])]
            phases = int(phase_rec.get('recommendation', '2'))

            # Estimate cost
            cost_est = self.estimate_cost(recommended_models, task_type, phases)

            # Assess risk
            failure_analysis = self.analytics.failure_analysis(task_type)
            risk_level = 'low' if failure_analysis.get('failure_count', 0) < 3 else \
                        'medium' if failure_analysis.get('failure_count', 0) < 8 else 'high'

            return {
                'task_type': task_type,
                'scope': scope,
                'budget': budget,
                'recommendation': {
                    'models': recommended_models,
                    'phases': phases,
                    'estimated_cost': cost_est.get('total_all_phases', 0.0),
                    'risk_level': risk_level,
                    'confidence': min(
                        model_rec.get('confidence', 0.0),
                        min(0.9, phases)  # More phases = higher confidence
                    )
                },
                'details': {
                    'models': model_rec,
                    'phases': phase_rec,
                    'cost': cost_est,
                    'risks': failure_analysis
                }
            }

        except Exception as e:
            logger.error(f"Error generating full recommendation: {e}")
            return {'error': str(e)}


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
