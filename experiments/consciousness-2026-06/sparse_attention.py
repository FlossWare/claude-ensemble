#!/usr/bin/env python3
"""Sparse Attention: Fixed sparsity patterns"""
import numpy as np

class SparseAttention:
    def __init__(self, block_size=64):
        self.block_size = block_size
    
    def create_sparse_mask(self, seq_len):
        """Block-diagonal + strided pattern"""
        mask = np.ones((seq_len, seq_len)) * -np.inf
        
        # Local blocks (diagonal)
        for i in range(0, seq_len, self.block_size):
            end = min(i + self.block_size, seq_len)
            mask[i:end, i:end] = 0
        
        # Strided attention (every block_size tokens)
        for i in range(seq_len):
            mask[i, ::self.block_size] = 0
        
        return mask
    
    def forward(self, Q, K, V):
        seq_len = Q.shape[0]
        scores = Q @ K.T
        mask = self.create_sparse_mask(seq_len)
        scores = scores + mask
        attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
        return attn @ V

if __name__ == '__main__':
    sparse = SparseAttention(block_size=4)
    Q = K = V = np.random.randn(16, 64)
    output = sparse.forward(Q, K, V)
    print(f"✅ Sparse Attention: {output.shape}")
