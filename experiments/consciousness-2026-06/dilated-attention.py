#!/usr/bin/env python3
"""Dilated Attention: Exponentially growing gaps"""
import numpy as np

class DilatedAttention:
    def __init__(self, dilation_rates=[1, 2, 4, 8]):
        self.dilation_rates = dilation_rates
    
    def create_dilated_mask(self, seq_len, dilation):
        """Attend to every dilation-th token"""
        mask = np.ones((seq_len, seq_len)) * -np.inf
        for i in range(seq_len):
            # Attend to positions at dilation intervals
            positions = range(0, i+1, dilation)
            mask[i, list(positions)] = 0
        return mask
    
    def forward(self, Q, K, V, layer_idx):
        """Use different dilation per layer"""
        dilation = self.dilation_rates[layer_idx % len(self.dilation_rates)]
        seq_len = Q.shape[0]
        
        scores = Q @ K.T
        mask = self.create_dilated_mask(seq_len, dilation)
        scores = scores + mask
        attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
        return attn @ V

if __name__ == '__main__':
    dilated = DilatedAttention(dilation_rates=[1, 2, 4])
    Q = K = V = np.random.randn(16, 64)
    output = dilated.forward(Q, K, V, layer_idx=1)
    print(f"✅ Dilated Attention: {output.shape}")
