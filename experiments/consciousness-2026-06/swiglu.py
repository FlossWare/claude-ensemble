#!/usr/bin/env python3
"""SwiGLU: Swish-Gated Linear Unit - used in LLaMA, PaLM"""
import numpy as np

class SwiGLU:
    def __init__(self, dim, hidden_dim):
        self.dim = dim
        self.hidden_dim = hidden_dim
    
    def swish(self, x):
        """Swish activation: x * sigmoid(x)"""
        return x * (1 / (1 + np.exp(-x)))
    
    def forward(self, x):
        """SwiGLU(x) = Swish(xW) ⊙ (xV)"""
        # Simulate two linear projections
        gate = self.swish(x)  # xW then swish
        value = x  # xV
        return gate * value

if __name__ == '__main__':
    swiglu = SwiGLU(dim=512, hidden_dim=2048)
    x = np.random.randn(10, 512)
    output = swiglu.forward(x)
    print(f"✅ SwiGLU: {output.shape}")
