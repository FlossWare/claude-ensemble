#!/usr/bin/env python3
"""
Integration Example: Using Decision Support with Arbitration

Shows how to use LearningAnalytics, ArbitrationAdvisor, and DiagnosticQueries
together to make informed arbitration decisions.

Workflow:
  1. User wants to run a code review
  2. Ask advisor: which models and how many phases?
  3. Run arbitration with recommended config
  4. After completion: query diagnostics for insights
  5. Update learning system (add outcomes to graph)

This is how humans interact with the learning system.
"""

import json
import logging
from typing import Dict, List, Any, Optional

from arbitration_advisor import ArbitrationAdvisor
from diagnostic_queries import DiagnosticQueries
from learning_analytics import LearningAnalytics

logger = logging.getLogger(__name__)


class ArbitrationDecisionWorkflow:
    """Full workflow: recommend config → run → analyze → learn"""

    def __init__(self):
        self.advisor = ArbitrationAdvisor()
        self.diagnostics = DiagnosticQueries()
        self.analytics = LearningAnalytics()

    def pre_execution_decision(self, task_type: str, scope: str = 'medium',
                              budget: float = None) -> Dict[str, Any]:
        """Step 1: Ask advisor what configuration to use.

        Returns: recommended models, phases, estimated cost, risk level
        """
        logger.info(f"Getting pre-execution recommendation for {task_type} ({scope})")

        recommendation = self.advisor.full_recommendation(task_type, scope, budget)

        if 'error' not in recommendation:
            rec = recommendation.get('recommendation', {})
            logger.info(f"Recommendation: {rec['models']}, {rec['phases']} phases, "
                       f"${rec['estimated_cost']:.2f}, confidence={rec['confidence']:.0%}")

        return recommendation

    def post_execution_analysis(self, task_type: str,
                               outcome: Dict[str, Any]) -> Dict[str, Any]:
        """Step 2: After arbitration, analyze what happened.

        Questions to answer:
        - Did we pick the right models?
        - Was the cost reasonable?
        - Did the outcome match expectations?
        - What would improve this?
        """
        logger.info(f"Analyzing outcome for {task_type}")

        analysis = {
            'task_type': task_type,
            'timestamp': outcome.get('timestamp'),
            'outcome': outcome.get('outcome'),  # success, inconclusive, failed
            'cost': outcome.get('total_cost'),
            'confidence': outcome.get('confidence'),
        }

        # Query best models to see if we could have done better
        best_models = self.analytics.best_models_for(task_type, limit=5)
        analysis['best_models_available'] = best_models

        # Check if used models are in top performers
        used_models = outcome.get('used_models', [])
        top_performers = [m['model'] for m in best_models[:3]]
        analysis['used_optimal_models'] = any(m in top_performers for m in used_models)

        # Failure analysis if needed
        if outcome.get('outcome') == 'failed':
            failure_analysis = self.analytics.failure_analysis(task_type)
            analysis['failure_patterns'] = failure_analysis
            analysis['recommendation'] = 'Consider using Opus for higher confidence'

        return analysis

    def investigate_problem(self, query: str) -> Dict[str, Any]:
        """Step 3: Investigate a specific problem.

        Examples:
        - "Why are security audits expensive?"
        - "Is Sonnet struggling with code reviews?"
        - "What's the trend for large scope tasks?"
        """
        logger.info(f"Investigating: {query}")

        investigation = {
            'query': query,
            'approaches': []
        }

        # Semantic search for related outcomes
        semantic_results = self.diagnostics.semantic_search(query, limit=20)
        investigation['semantic_search'] = semantic_results

        # If query mentions a model, analyze its patterns
        for model in ['sonnet', 'opus', 'haiku', 'flash', 'gemini']:
            if model in query.lower():
                patterns = self.diagnostics.find_model_patterns(model)
                investigation['model_patterns'] = {model: patterns}

        # If query mentions a task type, get analytics
        for task in ['code_review', 'security_audit', 'bug_analysis', 'design_validation']:
            if task in query.lower():
                analytics = self.analytics.cost_quality_tradeoff(task)
                investigation['task_analysis'] = {task: analytics}

        return investigation

    def continuous_learning_loop(self, arbitration_outcome: Dict[str, Any]) -> bool:
        """Step 4: Add outcome to learning system.

        After each arbitration:
        1. Parse outcome
        2. Add nodes/edges to graph
        3. Update Thompson with signals
        4. Trigger analytics refresh

        (This is typically done by Learning Service daemon)
        """
        try:
            # This would normally call:
            # - graph_outcomes_bridge.add_model_success_edges(...)
            # - arbitration_outcomes_bridge.send_signals_to_thompson(...)
            # - learning_orchestrator.sync_all_outcomes()

            logger.info("Learning loop would update graph and Thompson here")
            return True

        except Exception as e:
            logger.error(f"Error in learning loop: {e}")
            return False

    def full_workflow_example(self, task_type: str, scope: str = 'medium',
                             budget: float = None) -> Dict[str, Any]:
        """Run complete workflow: recommend → analyze → learn.

        Shows how all pieces work together.
        """
        logger.info(f"=== Full Workflow: {task_type} ({scope}) ===\n")

        result = {}

        # Step 1: Pre-execution
        logger.info("Step 1: Get execution recommendation")
        recommendation = self.pre_execution_decision(task_type, scope, budget)
        result['recommendation'] = recommendation
        print(json.dumps(recommendation, indent=2))

        # Step 2: Simulate execution
        logger.info("\nStep 2: [Would run arbitration with recommended config]")
        simulated_outcome = {
            'task_type': task_type,
            'timestamp': '2026-09-30T12:00:00',
            'outcome': 'success',
            'total_cost': 0.25,
            'confidence': 0.92,
            'used_models': recommendation.get('recommendation', {}).get('models', [])
        }
        result['outcome'] = simulated_outcome

        # Step 3: Post-execution analysis
        logger.info("\nStep 3: Analyze outcome")
        analysis = self.post_execution_analysis(task_type, simulated_outcome)
        result['analysis'] = analysis
        print(json.dumps(analysis, indent=2))

        # Step 4: Learning
        logger.info("\nStep 4: Update learning system")
        self.continuous_learning_loop(simulated_outcome)

        return result


def main():
    """Demo workflow"""
    logging.basicConfig(level=logging.INFO)

    workflow = ArbitrationDecisionWorkflow()

    # Example: code review workflow
    print("\n" + "="*70)
    print("EXAMPLE 1: Code Review (small scope, $0.50 budget)")
    print("="*70 + "\n")

    rec = workflow.pre_execution_decision('code_review', 'small', budget=0.50)
    print("Recommendation:")
    print(json.dumps(rec.get('recommendation', {}), indent=2))

    # Example: investigation
    print("\n" + "="*70)
    print("EXAMPLE 2: Investigate 'Why are Opus runs expensive?'")
    print("="*70 + "\n")

    investigation = workflow.investigate_problem('Why are Opus runs expensive?')
    print("Investigation results:")
    for key, value in investigation.items():
        if key != 'query' and isinstance(value, dict):
            print(f"\n{key}:")
            print(json.dumps(value, indent=2, default=str))

    # Example: post-execution
    print("\n" + "="*70)
    print("EXAMPLE 3: Post-Execution Analysis")
    print("="*70 + "\n")

    outcome = {
        'task_type': 'security_audit',
        'outcome': 'success',
        'total_cost': 0.42,
        'confidence': 0.88,
        'used_models': ['sonnet', 'opus', 'haiku']
    }

    analysis = workflow.post_execution_analysis('security_audit', outcome)
    print("Analysis:")
    print(json.dumps(analysis, indent=2, default=str))

    print("\n" + "="*70)
    print("All decision support queries working!")
    print("="*70)


if __name__ == '__main__':
    main()
