#!/usr/bin/env python3
"""Mixture of Depths (MoD): Conditional computation per token"""
import numpy as np

class MixtureOfDepths:
    def __init__(self, num_layers=24, capacity=0.5):
        self.num_layers = num_layers
        self.capacity = capacity  # Fraction of tokens that go deep
    
    def route_tokens(self, tokens, scores):
        """Select which tokens use each layer"""
        num_tokens = len(tokens)
        capacity_per_layer = int(num_tokens * self.capacity)
        
        # Top-k tokens by score use this layer
        top_k_indices = np.argsort(scores)[-capacity_per_layer:]
        
        return top_k_indices
    
    def forward(self, x, layers):
        """Process with conditional depth"""
        active = np.arange(len(x))  # All tokens start active
        
        for layer in layers:
            # Route: which tokens use this layer?
            scores = np.random.rand(len(x))  # Simulate routing scores
            routed = self.route_tokens(x, scores)
            
            # Only process routed tokens
            x[routed] = x[routed] * 1.1  # Simulate layer computation
        
        return x
    
    def compute_savings(self):
        """FLOPs reduction"""
        return f"{1 - self.capacity:.0%} FLOPs saved"

if __name__ == '__main__':
    mod = MixtureOfDepths(num_layers=24, capacity=0.5)
    x = np.random.randn(100, 512)
    # Simulate layers
    layers = [lambda x: x] * 24
    output = mod.forward(x, layers)
    print(f"✅ MoD: {output.shape}, savings: {mod.compute_savings()}")
