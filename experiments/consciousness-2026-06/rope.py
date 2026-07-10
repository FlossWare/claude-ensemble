#!/usr/bin/env python3
"""Rotary Position Embeddings (RoPE) - used in LLaMA, GPT-NeoX"""
import numpy as np

class RoPE:
    def __init__(self, dim, max_seq_len=2048, base=10000):
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base
        # Precompute frequencies
        inv_freq = 1.0 / (base ** (np.arange(0, dim, 2) / dim))
        self.inv_freq = inv_freq
    
    def apply(self, x, position):
        """Apply rotary embeddings to queries/keys"""
        # x shape: (seq_len, dim)
        freqs = position * self.inv_freq
        emb = np.concatenate([freqs, freqs], axis=-1)
        cos = np.cos(emb)
        sin = np.sin(emb)
        
        # Rotate: [x0, x1, ...] → [x0*cos - x1*sin, x0*sin + x1*cos, ...]
        x_rotated = x * cos + self.rotate_half(x) * sin
        return x_rotated
    
    def rotate_half(self, x):
        """Split and swap for rotation"""
        d = x.shape[-1] // 2
        return np.concatenate([-x[..., d:], x[..., :d]], axis=-1)

if __name__ == '__main__':
    rope = RoPE(dim=64)
    x = np.random.randn(10, 64)
    positions = np.arange(10).reshape(-1, 1)
    rotated = rope.apply(x, positions)
    print(f"✅ RoPE: {rotated.shape}")
