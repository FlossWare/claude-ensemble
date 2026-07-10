#!/usr/bin/env python3
"""ALiBi: Attention with Linear Biases - used in BLOOM"""
import numpy as np

class ALiBi:
    def __init__(self, num_heads=8):
        self.num_heads = num_heads
        # Geometric sequence of slopes
        slopes = 2 ** (-8 / num_heads * np.arange(1, num_heads + 1))
        self.slopes = slopes
    
    def get_bias(self, seq_len):
        """Compute position bias matrix"""
        # Distance matrix
        positions = np.arange(seq_len)
        distances = positions[:, None] - positions[None, :]
        
        # Apply head-specific slopes
        biases = []
        for slope in self.slopes:
            bias = -slope * np.abs(distances)
            biases.append(bias)
        
        return np.stack(biases)  # (num_heads, seq_len, seq_len)
    
    def apply(self, attention_scores):
        """Add bias to attention scores"""
        seq_len = attention_scores.shape[-1]
        bias = self.get_bias(seq_len)
        return attention_scores + bias

if __name__ == '__main__':
    alibi = ALiBi(num_heads=8)
    scores = np.random.randn(8, 10, 10)
    biased = alibi.apply(scores)
    print(f"✅ ALiBi: {biased.shape}")
