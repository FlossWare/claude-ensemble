#!/usr/bin/env python3
"""Linformer: Project K,V to lower dimension"""
import numpy as np

class Linformer:
    def __init__(self, seq_len, k=256):
        self.seq_len = seq_len
        self.k = k  # Projection dimension
        # Projection matrices
        self.E = np.random.randn(k, seq_len) / np.sqrt(seq_len)
        self.F = np.random.randn(k, seq_len) / np.sqrt(seq_len)
    
    def forward(self, Q, K, V):
        """Project K,V from seq_len to k"""
        # K: (seq_len, dim) → (k, dim)
        K_proj = self.E @ K
        V_proj = self.F @ V
        
        # Attention with projected K,V
        scores = Q @ K_proj.T  # (seq_len, k)
        attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
        output = attn @ V_proj  # (seq_len, dim)
        
        return output

if __name__ == '__main__':
    linformer = Linformer(seq_len=1024, k=256)
    Q = K = V = np.random.randn(1024, 64)
    output = linformer.forward(Q, K, V)
    print(f"✅ Linformer: {output.shape}, O(n) complexity")
