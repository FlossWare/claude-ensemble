#!/usr/bin/env python3
"""BigBird: Sparse attention with random + window + global"""
import numpy as np

class BigBird:
    def __init__(self, window_size=128, num_random=64, num_global=32):
        self.window_size = window_size
        self.num_random = num_random
        self.num_global = num_global
    
    def create_mask(self, seq_len):
        """Combine local + random + global"""
        mask = np.ones((seq_len, seq_len)) * -np.inf
        
        # Local sliding window
        for i in range(seq_len):
            start = max(0, i - self.window_size)
            end = min(seq_len, i + self.window_size)
            mask[i, start:end] = 0
        
        # Random attention
        for i in range(seq_len):
            random_indices = np.random.choice(seq_len, self.num_random, replace=False)
            mask[i, random_indices] = 0
        
        # Global tokens
        mask[:self.num_global, :] = 0
        mask[:, :self.num_global] = 0
        
        return mask
    
    def forward(self, Q, K, V):
        seq_len = Q.shape[0]
        scores = Q @ K.T
        mask = self.create_mask(seq_len)
        scores = scores + mask
        attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
        return attn @ V

if __name__ == '__main__':
    bigbird = BigBird(window_size=8, num_random=4, num_global=2)
    Q = K = V = np.random.randn(32, 64)
    output = bigbird.forward(Q, K, V)
    print(f"✅ BigBird: {output.shape}")
