#!/usr/bin/env python3
"""Memory Optimization Techniques"""

class GradientCheckpointing:
    """Trade compute for memory - recompute activations"""
    def __init__(self, checkpoint_every=4):
        self.checkpoint_every = checkpoint_every
        self.saved_activations = []
    
    def forward(self, layers, x):
        activations = [x]
        for i, layer in enumerate(layers):
            x = layer(x)
            if i % self.checkpoint_every == 0:
                self.saved_activations.append(x)
        return x

class MixedPrecision:
    """Use fp16 for forward/backward, fp32 for weights"""
    def cast_fp16(self, tensor):
        return tensor.astype('float16') if hasattr(tensor, 'astype') else tensor
    
    def cast_fp32(self, tensor):
        return tensor.astype('float32') if hasattr(tensor, 'astype') else tensor

if __name__ == '__main__':
    import numpy as np
    
    # Simulate layers
    layers = [lambda x: x * 1.1 for _ in range(8)]
    
    cp = GradientCheckpointing(checkpoint_every=4)
    x = np.array([1.0])
    result = cp.forward(layers, x)
    print(f"✅ Checkpointing: saved {len(cp.saved_activations)} checkpoints")
    
    mp = MixedPrecision()
    fp16 = mp.cast_fp16(np.array([1.0, 2.0, 3.0]))
    print(f"✅ Mixed precision: fp16 dtype={fp16.dtype}")
