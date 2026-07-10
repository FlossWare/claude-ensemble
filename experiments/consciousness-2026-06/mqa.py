#!/usr/bin/env python3
"""MQA: Multi-Query Attention - single K/V for all heads"""
import numpy as np

class MultiQueryAttention:
    def __init__(self, num_heads=32):
        self.num_heads = num_heads
    
    def forward(self, Q, K, V):
        """Q has num_heads, K/V shared across all heads"""
        # Q: (num_heads, seq_len, dim)
        # K, V: (1, seq_len, dim) - shared!
        
        outputs = []
        for q in Q:
            scores = q @ K[0].T
            attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
            output = attn @ V[0]
            outputs.append(output)
        
        return np.stack(outputs)
    
    def memory_savings(self):
        return f"{self.num_heads}× smaller KV cache vs MHA"

if __name__ == '__main__':
    mqa = MultiQueryAttention(num_heads=32)
    Q = np.random.randn(32, 10, 64)
    K = V = np.random.randn(1, 10, 64)
    output = mqa.forward(Q, K, V)
    print(f"✅ MQA: {output.shape}, savings: {mqa.memory_savings()}")
