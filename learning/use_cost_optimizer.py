#!/usr/bin/env python3
"""
Cost Optimizer Usage Module

Load and use the trained cost optimizer to:
- Predict costs for tasks
- Suggest cheaper alternatives
- Get cost-saving recommendations
"""

import pickle
from pathlib import Path
import json

def load_optimizer():
    """Load the trained cost optimizer model"""
    model_path = Path.home() / '.claude' / 'learning' / 'cost_optimizer.pkl'
    with open(model_path, 'rb') as f:
        return pickle.load(f)

def load_patterns():
    """Load just the patterns (doesn't require pickle)"""
    patterns_path = Path.home() / '.claude' / 'learning' / 'cost_optimizer_patterns.json'
    with open(patterns_path, 'r') as f:
        return json.load(f)

def get_cheaper_alternative(model, patterns=None):
    """Get the cheapest alternative to a model"""
    if patterns is None:
        patterns = load_patterns()

    for sub in patterns['substitutions']:
        if sub['expensive_model'] == model:
            return {
                'alternative': sub['cheap_model'],
                'savings_usd': sub['cost_savings_usd'],
                'savings_pct': sub['savings_pct'],
                'current_cost': sub['expensive_avg_cost'],
                'new_cost': sub['cheap_avg_cost']
            }
    return None

def get_model_cost(model, patterns=None):
    """Get average cost per execution for a model"""
    if patterns is None:
        patterns = load_patterns()

    if model in patterns['model_costs']:
        return patterns['model_costs'][model]['avg_cost_per_exec']
    return None

def get_all_substitutions(patterns=None):
    """Get all cost-saving substitutions"""
    if patterns is None:
        patterns = load_patterns()

    return patterns['substitutions']

def print_savings_report():
    """Print a formatted savings report"""
    patterns = load_patterns()

    print("=" * 70)
    print("COST OPTIMIZATION REPORT")
    print("=" * 70)

    print("\nModel Pricing ($/token):")
    print("-" * 70)
    for model, price in sorted(patterns['model_pricing'].items(), key=lambda x: x[1]):
        cost_data = patterns['model_costs'][model]
        print(f"  {model:30s} ${price:.8f}  (avg ${cost_data['avg_cost_per_exec']:.4f}/exec)")

    print("\n\nTop Cost-Saving Opportunities:")
    print("-" * 70)
    for i, sub in enumerate(patterns['substitutions'][:5], 1):
        print(f"\n{i}. Replace '{sub['expensive_model']}' with '{sub['cheap_model']}'")
        print(f"   Current cost: ${sub['expensive_avg_cost']:.4f} per execution")
        print(f"   New cost:     ${sub['cheap_avg_cost']:.4f} per execution")
        print(f"   Savings:      ${sub['cost_savings_usd']:.4f} per execution ({sub['savings_pct']:.1f}%)")
        print(f"   Used:         {sub['expensive_executions']} times")
        print(f"   Total potential: ${sub['cost_savings_usd'] * sub['expensive_executions']:.2f}")

if __name__ == '__main__':
    print_savings_report()
