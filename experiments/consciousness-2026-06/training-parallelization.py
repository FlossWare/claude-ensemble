#!/usr/bin/env python3
"""Training Parallelization Strategies"""

class DataParallel:
    """Split batch across GPUs"""
    def __init__(self, num_gpus=4):
        self.num_gpus = num_gpus
    
    def split_batch(self, batch, batch_size):
        per_gpu = batch_size // self.num_gpus
        splits = []
        for i in range(self.num_gpus):
            start = i * per_gpu
            end = start + per_gpu
            splits.append((start, end))
        return splits

class ModelParallel:
    """Split model across GPUs"""
    def __init__(self, num_gpus=4):
        self.num_gpus = num_gpus
    
    def split_model(self, num_layers):
        layers_per_gpu = num_layers // self.num_gpus
        return [(i * layers_per_gpu, (i+1) * layers_per_gpu) 
                for i in range(self.num_gpus)]

if __name__ == '__main__':
    dp = DataParallel(num_gpus=4)
    splits = dp.split_batch(None, batch_size=64)
    print(f"✅ Data Parallel: {len(splits)} splits of {splits[0]}")
    
    mp = ModelParallel(num_gpus=4)
    layer_splits = mp.split_model(num_layers=24)
    print(f"✅ Model Parallel: {len(layer_splits)} splits")
