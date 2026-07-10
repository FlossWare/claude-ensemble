#!/usr/bin/env python3
"""Sliding Window Attention - used in Mistral"""
import numpy as np

class SlidingWindowAttention:
    def __init__(self, window_size=256):
        self.window_size = window_size
    
    def create_mask(self, seq_len):
        """Create causal + window mask"""
        mask = np.ones((seq_len, seq_len)) * -np.inf
        for i in range(seq_len):
            start = max(0, i - self.window_size)
            end = i + 1
            mask[i, start:end] = 0
        return mask
    
    def forward(self, Q, K, V):
        """Attention with sliding window"""
        seq_len = Q.shape[0]
        scores = Q @ K.T
        mask = self.create_mask(seq_len)
        scores = scores + mask
        attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
        output = attn @ V
        return output

if __name__ == '__main__':
    swa = SlidingWindowAttention(window_size=4)
    Q = K = V = np.random.randn(10, 64)
    output = swa.forward(Q, K, V)
    print(f"✅ Sliding Window: {output.shape}")
