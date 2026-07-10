#!/usr/bin/env python3
"""Local Attention: Fixed-size local windows"""
import numpy as np

class LocalAttention:
    def __init__(self, window_size=128):
        self.window_size = window_size
    
    def forward(self, Q, K, V):
        """Each token attends to local neighborhood"""
        seq_len = Q.shape[0]
        output = np.zeros_like(V)
        
        for i in range(seq_len):
            start = max(0, i - self.window_size // 2)
            end = min(seq_len, i + self.window_size // 2)
            
            # Attend to local window
            scores = Q[i:i+1] @ K[start:end].T
            attn = np.exp(scores) / np.exp(scores).sum()
            output[i] = attn @ V[start:end]
        
        return output

if __name__ == '__main__':
    local = LocalAttention(window_size=8)
    Q = K = V = np.random.randn(32, 64)
    output = local.forward(Q, K, V)
    print(f"✅ Local Attention: {output.shape}")
