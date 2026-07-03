#!/usr/bin/env python3
"""
Integrated Router: Context Fusion + Contextual Bandit

Combines multi-source context fusion with LinUCB bandit for
intelligent model selection that considers:
- Task type and complexity
- Session history and patterns
- User preferences
- Temporal patterns
- Resource availability

Usage:
    router = IntegratedRouter()
    selection = router.select_model(
        task_type='code_review',
        task_description='Review Java Maven code',
        complexity=0.6
    )
    print(f"Selected: {selection['model']}")
"""

import sys
from pathlib import Path
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

# Import context fusion model
sys.path.insert(0, str(Path(__file__).parent))
from context_fusion_model import ContextFusionModel


class IntegratedRouter:
    """
    Production router combining context fusion with contextual bandits.

    Architecture:
    1. Context Fusion: Combines multiple context sources into rich embedding
    2. Contextual Bandit: Uses fused context for model selection (LinUCB)
    3. Feedback Loop: Updates both fusion weights and bandit parameters
    """

    def __init__(self, learning_dir: Path = None):
        """
        Args:
            learning_dir: Directory containing learned models
        """
        if learning_dir is None:
            learning_dir = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning'

        self.learning_dir = learning_dir

        # Load context fusion model
        fusion_model_path = learning_dir / 'context_fusion_model.pkl'
        self.fusion_model = ContextFusionModel(embedding_dim=128)

        if fusion_model_path.exists():
            self.fusion_model.load_model(str(fusion_model_path))
            print(f"Loaded context fusion model from {fusion_model_path}")
        else:
            print("Warning: No pre-trained fusion model found, using random initialization")

        # Simplified contextual bandit (LinUCB)
        self.bandit_arms = {}  # model -> LinUCB parameters
        self.alpha = 1.0  # Exploration parameter

        # Available models (from fleet configuration)
        self.available_models = [
            'sonnet',
            'haiku',
            'opus',
            'gpt-4o',
            'gemini-pro',
            'multi-model-adversarial'
        ]

        # Initialize bandit arms
        for model in self.available_models:
            self._init_arm(model)

        # Cost model (for budget-aware selection)
        self.cost_model = {
            'sonnet': {'input': 3.0, 'output': 15.0},
            'haiku': {'input': 0.25, 'output': 1.25},
            'opus': {'input': 15.0, 'output': 75.0},
            'gpt-4o': {'input': 2.5, 'output': 10.0},
            'gemini-pro': {'input': 0.5, 'output': 1.5},
            'multi-model-adversarial': {'input': 3.0, 'output': 15.0}
        }

        # Quality thresholds per task type
        self.quality_thresholds = self._load_quality_thresholds()

    def _load_quality_thresholds(self) -> Dict[str, float]:
        """Load quality thresholds from learning directory"""
        default_thresholds = {
            'code_review': 0.7,
            'debugging': 0.6,
            'build_tasks': 0.65,
            'containerization': 0.65,
            'migration': 0.7,
            'default': 0.6
        }

        thresholds_path = self.learning_dir / 'quality_thresholds.json'
        if thresholds_path.exists():
            with open(thresholds_path) as f:
                data = json.load(f)
                loaded = data.get('thresholds', {})
                # Merge with defaults
                return {**default_thresholds, **loaded}

        return default_thresholds

    def _init_arm(self, model: str):
        """Initialize LinUCB parameters for a model"""
        d = 128  # Context dimension (matches fusion model)
        self.bandit_arms[model] = {
            'A': np.identity(d),
            'b': np.zeros(d),
            'A_inv': np.identity(d),
            'n_observations': 0
        }

    def _estimate_cost(self, model: str, estimated_tokens: int) -> float:
        """Estimate cost for a model given estimated token count"""
        if model not in self.cost_model:
            return 0.0

        pricing = self.cost_model[model]
        # Assume 70% input, 30% output
        input_tokens = int(estimated_tokens * 0.7)
        output_tokens = int(estimated_tokens * 0.3)

        return (input_tokens * pricing['input'] + output_tokens * pricing['output']) / 1_000_000

    def select_model(self,
                    task_type: str,
                    task_description: str = "",
                    complexity: float = None,
                    min_quality: float = None,
                    max_cost: float = 0.01,
                    fleet_health: float = 1.0,
                    cost_budget: float = 1.0) -> Dict:
        """
        Select best model for task using context fusion + bandit.

        Args:
            task_type: Type of task (code_review, debugging, etc.)
            task_description: Detailed task description
            complexity: Task complexity [0, 1] (auto-estimated if None)
            min_quality: Minimum quality threshold (uses defaults if None)
            max_cost: Maximum acceptable cost per request
            fleet_health: Overall fleet health [0, 1]
            cost_budget: Remaining budget [0, 1]

        Returns:
            Selection details including:
            - model: Selected model name
            - confidence: Selection confidence
            - ucb_score: UCB score
            - estimated_cost: Estimated cost
            - reasoning: Explanation of selection
            - alternatives: Other candidate models with scores
        """
        # Auto-estimate complexity if not provided
        if complexity is None:
            complexity = self._estimate_complexity(task_type, task_description)

        # Get quality threshold
        if min_quality is None:
            min_quality = self.quality_thresholds.get(task_type,
                                                     self.quality_thresholds['default'])

        # Fuse contexts
        fused_context, attention_weights = self.fusion_model.fuse_contexts(
            task_type=task_type,
            complexity=complexity,
            timestamp=datetime.now(),
            fleet_health=fleet_health,
            cost_budget=cost_budget
        )

        # Select arm using LinUCB
        best_model = None
        best_score = -float('inf')
        all_scores = {}

        for model in self.available_models:
            arm = self.bandit_arms[model]

            # LinUCB score
            theta = arm['A_inv'] @ arm['b']
            expected_reward = theta.T @ fused_context
            uncertainty = self.alpha * np.sqrt(fused_context.T @ arm['A_inv'] @ fused_context)
            ucb_score = expected_reward + uncertainty

            # Estimate cost
            est_tokens = int(len(task_description.split()) * 1.3 * 100)  # Rough estimate
            est_cost = self._estimate_cost(model, est_tokens)

            # Apply cost constraint
            if est_cost > max_cost:
                ucb_score -= 10.0  # Heavy penalty for exceeding budget

            # Apply quality threshold (if we have enough observations)
            if arm['n_observations'] >= 5:
                avg_reward = arm['b'].sum() / arm['n_observations']
                if avg_reward < min_quality:
                    ucb_score -= 5.0  # Penalty for low quality

            all_scores[model] = {
                'ucb_score': float(ucb_score),
                'expected_reward': float(expected_reward),
                'uncertainty': float(uncertainty),
                'estimated_cost': est_cost,
                'n_observations': arm['n_observations']
            }

            if ucb_score > best_score:
                best_score = ucb_score
                best_model = model

        # Generate reasoning
        reasoning = self._generate_reasoning(
            best_model,
            task_type,
            complexity,
            attention_weights,
            all_scores[best_model]
        )

        return {
            'model': best_model,
            'confidence': float(np.tanh(best_score)),  # Map to [0, 1]
            'ucb_score': best_score,
            'estimated_cost': all_scores[best_model]['estimated_cost'],
            'reasoning': reasoning,
            'alternatives': all_scores,
            'fused_context_norm': float(np.linalg.norm(fused_context)),
            'attention_weights': attention_weights
        }

    def _estimate_complexity(self, task_type: str, task_description: str) -> float:
        """
        Auto-estimate task complexity.

        Uses heuristics based on:
        - Task type
        - Description length
        - Keywords indicating complexity
        """
        # Base complexity by task type
        base_complexity = {
            'debugging': 0.7,
            'code_review': 0.5,
            'build_tasks': 0.4,
            'containerization': 0.5,
            'migration': 0.6
        }
        complexity = base_complexity.get(task_type, 0.5)

        # Adjust based on description
        desc_len = len(task_description.split())
        if desc_len > 100:
            complexity += 0.1
        elif desc_len < 20:
            complexity -= 0.1

        # Keywords indicating high complexity
        high_complexity_keywords = [
            'complex', 'difficult', 'multiple', 'distributed',
            'concurrent', 'parallel', 'integration', 'architecture'
        ]
        desc_lower = task_description.lower()
        keyword_count = sum(1 for kw in high_complexity_keywords if kw in desc_lower)
        complexity += keyword_count * 0.05

        # Clip to valid range
        return max(0.0, min(1.0, complexity))

    def _generate_reasoning(self,
                           model: str,
                           task_type: str,
                           complexity: float,
                           attention_weights: Dict[str, float],
                           scores: Dict) -> str:
        """Generate human-readable reasoning for selection"""
        # Find most influential context source
        top_source = max(attention_weights.items(), key=lambda x: x[1])

        reasoning = f"Selected {model} for {task_type} task (complexity: {complexity:.2f}). "

        # Explain based on top context source
        if top_source[0] == 'session':
            reasoning += "Decision driven by session history patterns. "
        elif top_source[0] == 'task':
            reasoning += "Decision driven by task characteristics. "
        elif top_source[0] == 'user':
            reasoning += "Decision driven by user preferences. "
        elif top_source[0] == 'temporal':
            reasoning += "Decision driven by timing patterns. "
        elif top_source[0] == 'resource':
            reasoning += "Decision driven by resource availability. "

        # Add confidence info
        if scores['n_observations'] < 5:
            reasoning += f"Exploring (only {scores['n_observations']} observations). "
        else:
            reasoning += f"Based on {scores['n_observations']} observations. "

        reasoning += f"Expected reward: {scores['expected_reward']:.3f}, "
        reasoning += f"Cost: ${scores['estimated_cost']:.4f}"

        return reasoning

    def update(self, model: str, fused_context: np.ndarray, reward: float,
              primary_context_source: str = 'task'):
        """
        Update both fusion model and bandit based on observed reward.

        Args:
            model: Model that was used
            fused_context: Fused context that was used for selection
            reward: Observed reward [0, 1]
            primary_context_source: Which context source was most relevant
        """
        # Update contextual bandit (LinUCB)
        if model not in self.bandit_arms:
            self._init_arm(model)

        arm = self.bandit_arms[model]
        arm['A'] += np.outer(fused_context, fused_context)
        arm['b'] += reward * fused_context

        # Sherman-Morrison inverse update
        v = arm['A_inv'] @ fused_context
        denom = 1 + fused_context.T @ v
        if abs(denom) > 1e-10:
            arm['A_inv'] -= np.outer(v, v) / denom

        arm['n_observations'] += 1

        # Update context fusion attention weights
        self.fusion_model.update_attention_weights(
            primary_context_source,
            reward,
            lr=0.01
        )

    def save_state(self):
        """Save router state to disk"""
        # Save fusion model
        fusion_path = self.learning_dir / 'context_fusion_model.pkl'
        self.fusion_model.save_model(str(fusion_path))

        # Save bandit state
        bandit_state = {
            model: {
                'A': arm['A'].tolist(),
                'b': arm['b'].tolist(),
                'n_observations': arm['n_observations']
            }
            for model, arm in self.bandit_arms.items()
        }

        bandit_path = self.learning_dir / 'integrated_router_bandit_state.json'
        with open(bandit_path, 'w') as f:
            json.dump(bandit_state, f, indent=2)

        print(f"Saved router state to {self.learning_dir}")

    def load_state(self):
        """Load router state from disk"""
        # Load fusion model
        fusion_path = self.learning_dir / 'context_fusion_model.pkl'
        if fusion_path.exists():
            self.fusion_model.load_model(str(fusion_path))

        # Load bandit state
        bandit_path = self.learning_dir / 'integrated_router_bandit_state.json'
        if bandit_path.exists():
            with open(bandit_path) as f:
                bandit_state = json.load(f)

            for model, state in bandit_state.items():
                self.bandit_arms[model] = {
                    'A': np.array(state['A']),
                    'b': np.array(state['b']),
                    'A_inv': np.linalg.inv(np.array(state['A'])),
                    'n_observations': state['n_observations']
                }


def demo_integrated_router():
    """Demonstrate integrated router"""
    print("=" * 80)
    print("INTEGRATED ROUTER DEMONSTRATION")
    print("=" * 80)

    router = IntegratedRouter()

    # Example 1: Code review task
    print("\nExample 1: Java code review task")
    selection = router.select_model(
        task_type='code_review',
        task_description='Review Java Maven project with Salesforce integration',
        max_cost=0.01
    )

    print(f"\nSelected: {selection['model']}")
    print(f"Confidence: {selection['confidence']:.3f}")
    print(f"Estimated cost: ${selection['estimated_cost']:.4f}")
    print(f"Reasoning: {selection['reasoning']}")
    print("\nTop 3 alternatives:")
    sorted_alts = sorted(selection['alternatives'].items(),
                        key=lambda x: x[1]['ucb_score'],
                        reverse=True)[:3]
    for model, scores in sorted_alts:
        print(f"  {model}: UCB={scores['ucb_score']:.3f}, "
              f"Cost=${scores['estimated_cost']:.4f}")

    # Example 2: Debugging task
    print("\n" + "-" * 80)
    print("\nExample 2: High complexity debugging task")
    selection = router.select_model(
        task_type='debugging',
        task_description='Debug complex distributed system race condition with multiple concurrent processes',
        complexity=0.9,
        max_cost=0.02
    )

    print(f"\nSelected: {selection['model']}")
    print(f"Confidence: {selection['confidence']:.3f}")
    print(f"Estimated cost: ${selection['estimated_cost']:.4f}")
    print(f"Reasoning: {selection['reasoning']}")

    # Example 3: Budget-constrained task
    print("\n" + "-" * 80)
    print("\nExample 3: Budget-constrained build task")
    selection = router.select_model(
        task_type='build_tasks',
        task_description='Build Maven project',
        max_cost=0.002,  # Very low budget
        cost_budget=0.3  # Low remaining budget
    )

    print(f"\nSelected: {selection['model']}")
    print(f"Confidence: {selection['confidence']:.3f}")
    print(f"Estimated cost: ${selection['estimated_cost']:.4f}")
    print(f"Reasoning: {selection['reasoning']}")

    print("\nAttention weights (what influenced decision):")
    for source, weight in selection['attention_weights'].items():
        print(f"  {source}: {weight:.4f}")


if __name__ == '__main__':
    demo_integrated_router()
