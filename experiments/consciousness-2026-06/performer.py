#!/usr/bin/env python3
"""Performer: FAVOR+ kernel approximation"""
import numpy as np

class Performer:
    def __init__(self, num_features=256):
        self.num_features = num_features
    
    def kernel_feature_map(self, x):
        """Random Fourier features"""
        # Random projection
        omega = np.random.randn(x.shape[1], self.num_features) / np.sqrt(x.shape[1])
        projection = x @ omega
        
        # Positive random features
        return np.exp(projection - projection.max(axis=1, keepdims=True)) / np.sqrt(self.num_features)
    
    def forward(self, Q, K, V):
        """Linear attention via kernel trick"""
        Q_prime = self.kernel_feature_map(Q)
        K_prime = self.kernel_feature_map(K)
        
        # Linear complexity: (Q' @ (K'^T @ V))
        KV = K_prime.T @ V  # (num_features, dim)
        numerator = Q_prime @ KV  # (seq_len, dim)
        
        K_sum = K_prime.sum(axis=0, keepdims=True)  # (1, num_features)
        denominator = Q_prime @ K_sum.T  # (seq_len, 1)
        
        output = numerator / (denominator + 1e-6)
        return output

if __name__ == '__main__':
    performer = Performer(num_features=256)
    Q = K = V = np.random.randn(1024, 64)
    output = performer.forward(Q, K, V)
    print(f"✅ Performer: {output.shape}, O(n) complexity")
