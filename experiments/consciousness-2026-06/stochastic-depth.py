#!/usr/bin/env python3
"""Stochastic Depth: Randomly skip residual blocks"""
import numpy as np

class StochasticDepth:
    def __init__(self, drop_prob=0.1):
        self.drop_prob = drop_prob
    
    def forward(self, x, residual_fn, training=True):
        """Apply residual with probability (1 - drop_prob)"""
        if training and np.random.rand() < self.drop_prob:
            # Skip the residual block
            return x
        else:
            # Apply residual
            return x + residual_fn(x)

if __name__ == '__main__':
    stoch_depth = StochasticDepth(drop_prob=0.1)
    x = np.random.randn(10, 512)
    residual = lambda x: x * 0.1
    
    count_skipped = 0
    for _ in range(100):
        output = stoch_depth.forward(x, residual, training=True)
        if np.array_equal(output, x):
            count_skipped += 1
    
    print(f"✅ Stochastic Depth: skipped {count_skipped}/100 times (~10% expected)")
