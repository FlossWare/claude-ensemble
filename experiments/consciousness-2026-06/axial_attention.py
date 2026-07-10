#!/usr/bin/env python3
"""Axial Attention: Factorize 2D attention into row + column"""
import numpy as np

class AxialAttention:
    def __init__(self, height, width):
        self.height = height
        self.width = width
    
    def forward(self, x):
        """x: (height, width, dim)"""
        # Row attention
        row_output = np.zeros_like(x)
        for i in range(self.height):
            row = x[i]  # (width, dim)
            scores = row @ row.T
            attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
            row_output[i] = attn @ row
        
        # Column attention
        col_output = np.zeros_like(x)
        for j in range(self.width):
            col = x[:, j]  # (height, dim)
            scores = col @ col.T
            attn = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)
            col_output[:, j] = attn @ col
        
        # Combine
        return row_output + col_output

if __name__ == '__main__':
    axial = AxialAttention(height=8, width=8)
    x = np.random.randn(8, 8, 64)
    output = axial.forward(x)
    print(f"✅ Axial Attention: {output.shape}")
