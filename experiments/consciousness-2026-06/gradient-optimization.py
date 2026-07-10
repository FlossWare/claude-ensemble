#!/usr/bin/env python3
"""Gradient Optimization Strategies"""

class GradientClipping:
    def __init__(self, max_norm=1.0):
        self.max_norm = max_norm
    
    def clip(self, gradients):
        import numpy as np
        grad_norm = np.linalg.norm(gradients)
        if grad_norm > self.max_norm:
            return gradients * (self.max_norm / grad_norm)
        return gradients

class GradientAccumulation:
    def __init__(self, steps=4):
        self.steps = steps
        self.accumulated = None
    
    def accumulate(self, gradient, step):
        if self.accumulated is None:
            self.accumulated = gradient / self.steps
        else:
            self.accumulated += gradient / self.steps
        
        if (step + 1) % self.steps == 0:
            result = self.accumulated
            self.accumulated = None
            return result
        return None

if __name__ == '__main__':
    import numpy as np
    
    clip = GradientClipping(max_norm=1.0)
    grad = np.array([10.0, 20.0, 30.0])
    clipped = clip.clip(grad)
    print(f"✅ Clipping: {np.linalg.norm(clipped):.2f} (max 1.0)")
    
    accum = GradientAccumulation(steps=4)
    for i in range(4):
        result = accum.accumulate(grad, i)
    print(f"✅ Accumulation: {result is not None}")
