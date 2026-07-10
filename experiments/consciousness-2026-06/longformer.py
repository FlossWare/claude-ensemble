#!/usr/bin/env python3
"""Longformer: Local + Global attention"""
import numpy as np

class Longformer:
    def __init__(self, window_size=256, global_tokens=4):
        self.window_size = window_size
        self.global_tokens = global_tokens
    
    def create_mask(self, seq_len):
        """Local sliding window + global attention"""
        mask = np.ones((seq_len, seq_len)) * -np.inf
        
        # Local window
        for i in range(seq_len):
            start = max(0, i - self.window_size)
            end = min(seq_len, i + self.window_size)
            mask[i, start:end] = 0
        
        # Global tokens attend to everything
        mask[:self.global_tokens, :] = 0
        mask[:, :self.global_tokens] = 0
        
        return mask
    
    def forward(self, Q, K, V):
        seq_len = Q.shape[0]
        scores = Q @ K.T
        mask = self.create_mask(seq_len)
        scores = scores + mask
        attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
        return attn @ V

if __name__ == '__main__':
    longformer = Longformer(window_size=8, global_tokens=2)
    Q = K = V = np.random.randn(32, 64)
    output = longformer.forward(Q, K, V)
    print(f"✅ Longformer: {output.shape}")
