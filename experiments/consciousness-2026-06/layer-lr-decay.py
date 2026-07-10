#!/usr/bin/env python3
"""Layer-wise Learning Rate Decay - lower layers learn slower"""

class LayerwiseLRDecay:
    def __init__(self, base_lr=1e-4, num_layers=24, decay_rate=0.9):
        self.base_lr = base_lr
        self.num_layers = num_layers
        self.decay_rate = decay_rate
    
    def get_layer_lr(self, layer_idx):
        """Earlier layers get lower LR"""
        # Layer 0 (closest to input) gets most decay
        decay_factor = self.decay_rate ** (self.num_layers - layer_idx - 1)
        return self.base_lr * decay_factor
    
    def get_all_lrs(self):
        """Return LR for each layer"""
        return [self.get_layer_lr(i) for i in range(self.num_layers)]

if __name__ == '__main__':
    decay = LayerwiseLRDecay(base_lr=1e-4, num_layers=24, decay_rate=0.9)
    lrs = decay.get_all_lrs()
    print(f"✅ Layer LR Decay: layer_0={lrs[0]:.2e}, layer_23={lrs[23]:.2e}")
