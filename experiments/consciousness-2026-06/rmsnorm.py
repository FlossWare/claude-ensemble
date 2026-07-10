#!/usr/bin/env python3
"""RMSNorm: Root Mean Square Layer Normalization - used in LLaMA"""
import numpy as np

class RMSNorm:
    def __init__(self, dim, eps=1e-6):
        self.dim = dim
        self.eps = eps
        self.weight = np.ones(dim)
    
    def forward(self, x):
        """Normalize by RMS, no mean centering"""
        # RMS = sqrt(mean(x²))
        rms = np.sqrt(np.mean(x**2, axis=-1, keepdims=True) + self.eps)
        normalized = x / rms
        return self.weight * normalized

if __name__ == '__main__':
    rms = RMSNorm(dim=512)
    x = np.random.randn(10, 512)
    output = rms.forward(x)
    print(f"✅ RMSNorm: {output.shape}, mean={output.mean():.3f}, std={output.std():.3f}")
