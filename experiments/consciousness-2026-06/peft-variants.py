#!/usr/bin/env python3
"""PEFT Variants: LoRA, DoRA, and enhancements"""

class LoRA:
    """Low-Rank Adaptation - add trainable low-rank matrices"""
    def __init__(self, rank=8, alpha=16):
        self.rank = rank
        self.alpha = alpha
        self.scale = alpha / rank
    
    def forward(self, W, x, A, B):
        """W: frozen weights, A/B: trainable low-rank"""
        frozen = W @ x
        adapted = self.scale * (B @ (A @ x))
        return frozen + adapted

class DoRA:
    """Decomposed LoRA - magnitude + direction"""
    def __init__(self, rank=8):
        self.rank = rank
    
    def forward(self, W, x, A, B, m):
        """m: magnitude vector"""
        direction = W + (B @ A)
        magnitude = m
        return magnitude * (direction @ x)

class QLoRA:
    """Quantized LoRA - 4-bit base + LoRA"""
    def __init__(self, rank=8):
        self.rank = rank
    
    def dequantize(self, W_4bit):
        """Simulate 4-bit → fp16"""
        return W_4bit * 0.0625  # Simple scale

if __name__ == '__main__':
    import numpy as np
    lora = LoRA(rank=8)
    W = np.random.randn(512, 512)
    x = np.random.randn(512, 1)
    A = np.random.randn(8, 512)
    B = np.random.randn(512, 8)
    result = lora.forward(W, x, A, B)
    print(f"✅ LoRA: {result.shape}")
    
    dora = DoRA(rank=8)
    m = np.ones((512, 1))
    result = dora.forward(W, x, A, B, m)
    print(f"✅ DoRA: {result.shape}")
