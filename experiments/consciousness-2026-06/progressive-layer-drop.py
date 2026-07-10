#!/usr/bin/env python3
"""Progressive Layer Dropping: Skip layers during training"""
import numpy as np

class ProgressiveLayerDropping:
    def __init__(self, num_layers=24, drop_prob=0.2):
        self.num_layers = num_layers
        self.drop_prob = drop_prob
    
    def sample_layers_to_use(self):
        """Randomly select which layers to execute"""
        keep_mask = np.random.rand(self.num_layers) > self.drop_prob
        # Always keep first and last
        keep_mask[0] = True
        keep_mask[-1] = True
        return np.where(keep_mask)[0]
    
    def forward(self, x, layers):
        """Execute only sampled layers"""
        active_layers = self.sample_layers_to_use()
        
        for i in active_layers:
            x = layers[i](x)
        
        return x

if __name__ == '__main__':
    layer_drop = ProgressiveLayerDropping(num_layers=24, drop_prob=0.2)
    active = layer_drop.sample_layers_to_use()
    print(f"✅ Layer Dropping: using {len(active)}/24 layers")
