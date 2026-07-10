#!/usr/bin/env python3
"""Model Sharding Strategies"""

class TensorParallel:
    """Shard individual layers across devices"""
    def __init__(self, num_devices=8):
        self.num_devices = num_devices
    
    def shard_linear(self, weight_shape):
        """Shard weight matrix along columns"""
        rows, cols = weight_shape
        cols_per_device = cols // self.num_devices
        shards = [(rows, cols_per_device) for _ in range(self.num_devices)]
        return shards

class SequenceParallel:
    """Shard sequence dimension"""
    def __init__(self, num_devices=8):
        self.num_devices = num_devices
    
    def shard_sequence(self, seq_len):
        """Shard along sequence for LayerNorm etc"""
        tokens_per_device = seq_len // self.num_devices
        return [tokens_per_device] * self.num_devices

if __name__ == '__main__':
    tp = TensorParallel(num_devices=8)
    shards = tp.shard_linear((4096, 4096))
    print(f"✅ Tensor Parallel: {len(shards)} shards of {shards[0]}")
    
    sp = SequenceParallel(num_devices=8)
    seq_shards = sp.shard_sequence(2048)
    print(f"✅ Sequence Parallel: {len(seq_shards)} shards of {seq_shards[0]} tokens")
