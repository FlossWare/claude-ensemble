#!/usr/bin/env python3
"""GELU Variants: QuickGELU, NewGELU"""
import numpy as np

class GELUVariants:
    def gelu_exact(self, x):
        """Original GELU: x * Φ(x)"""
        return 0.5 * x * (1 + np.tanh(np.sqrt(2/np.pi) * (x + 0.044715 * x**3)))
    
    def quick_gelu(self, x):
        """QuickGELU: x * sigmoid(1.702 * x)"""
        return x * (1 / (1 + np.exp(-1.702 * x)))
    
    def new_gelu(self, x):
        """NewGELU: used in GPT-2"""
        return 0.5 * x * (1.0 + np.tanh(0.7978845608 * (x + 0.044715 * x**3)))

if __name__ == '__main__':
    gelu = GELUVariants()
    x = np.array([-1.0, 0.0, 1.0])
    exact = gelu.gelu_exact(x)
    quick = gelu.quick_gelu(x)
    new = gelu.new_gelu(x)
    print(f"✅ GELU variants: exact={exact[2]:.3f}, quick={quick[2]:.3f}, new={new[2]:.3f}")
