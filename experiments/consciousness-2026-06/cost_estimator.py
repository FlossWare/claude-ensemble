#!/usr/bin/env python3
"""Cost Estimator for AI Operations"""

class CostEstimator:
    def __init__(self):
        self.prices = {
            'opus': {'input': 15.0, 'output': 75.0},  # per 1M tokens
            'sonnet': {'input': 3.0, 'output': 15.0},
            'haiku': {'input': 0.25, 'output': 1.25},
            'local': {'input': 0.0, 'output': 0.0}
        }
    
    def estimate(self, model, input_tokens, output_tokens):
        """Estimate cost in dollars"""
        if model not in self.prices:
            return 0.0
        
        input_cost = (input_tokens / 1_000_000) * self.prices[model]['input']
        output_cost = (output_tokens / 1_000_000) * self.prices[model]['output']
        return input_cost + output_cost

if __name__ == '__main__':
    estimator = CostEstimator()
    cost = estimator.estimate('sonnet', 10000, 5000)
    print(f"✅ Cost Estimator: ${cost:.4f} for 10k in + 5k out")
