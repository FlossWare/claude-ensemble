#!/usr/bin/env python3
"""GQA: Grouped Query Attention - used in LLaMA 2"""
import numpy as np

class GroupedQueryAttention:
    def __init__(self, num_heads=32, num_kv_heads=8):
        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.num_groups = num_heads // num_kv_heads
    
    def forward(self, Q, K, V):
        """Q has num_heads, K/V have num_kv_heads"""
        # Repeat K/V for each group
        K_repeated = np.repeat(K, self.num_groups, axis=0)
        V_repeated = np.repeat(V, self.num_groups, axis=0)
        
        # Standard attention with repeated K/V
        scores = Q @ K_repeated.transpose(0, 2, 1)
        attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
        output = attn @ V_repeated
        
        return output
    
    def memory_savings(self):
        """KV cache reduction"""
        return f"{self.num_heads // self.num_kv_heads}× smaller KV cache"

if __name__ == '__main__':
    gqa = GroupedQueryAttention(num_heads=32, num_kv_heads=8)
    Q = np.random.randn(32, 10, 64)
    K = V = np.random.randn(8, 10, 64)
    output = gqa.forward(Q, K, V)
    print(f"✅ GQA: {output.shape}, savings: {gqa.memory_savings()}")
