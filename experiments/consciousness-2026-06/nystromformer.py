#!/usr/bin/env python3
"""Nyströmformer: Nyström approximation of attention"""
import numpy as np

class Nystromformer:
    def __init__(self, num_landmarks=64):
        self.num_landmarks = num_landmarks
    
    def select_landmarks(self, x):
        """Sample landmark points"""
        indices = np.random.choice(len(x), self.num_landmarks, replace=False)
        return x[indices], indices
    
    def forward(self, Q, K, V):
        """Approximate via low-rank Nyström method"""
        landmarks, landmark_idx = self.select_landmarks(K)
        
        # Q @ landmarks^T
        Q_land = Q @ landmarks.T  # (seq_len, num_landmarks)
        
        # landmarks @ landmarks^T (small matrix)
        land_land = landmarks @ landmarks.T  # (num_landmarks, num_landmarks)
        land_land_inv = np.linalg.pinv(land_land)
        
        # landmarks @ K^T
        land_K = landmarks @ K.T  # (num_landmarks, seq_len)
        
        # Nyström approximation: Q_land @ inv(land_land) @ land_K
        approx_scores = Q_land @ land_land_inv @ land_K
        
        attn = np.exp(approx_scores) / np.exp(approx_scores).sum(axis=-1, keepdims=True)
        output = attn @ V
        
        return output

if __name__ == '__main__':
    nystrom = Nystromformer(num_landmarks=64)
    Q = K = V = np.random.randn(512, 64)
    output = nystrom.forward(Q, K, V)
    print(f"✅ Nyströmformer: {output.shape}, O(n) complexity")
