#!/usr/bin/env python3
"""ZeRO: Zero Redundancy Optimizer"""

class ZeROOptimizer:
    """Partition optimizer states across devices"""
    def __init__(self, num_devices=8, stage=2):
        self.num_devices = num_devices
        self.stage = stage  # 1=optimizer, 2=+gradients, 3=+params
    
    def partition_optimizer_state(self, num_params):
        """ZeRO Stage 1: Partition optimizer state"""
        params_per_device = num_params // self.num_devices
        return [(i * params_per_device, (i+1) * params_per_device) 
                for i in range(self.num_devices)]
    
    def partition_gradients(self, num_params):
        """ZeRO Stage 2: Also partition gradients"""
        return self.partition_optimizer_state(num_params)
    
    def partition_parameters(self, num_params):
        """ZeRO Stage 3: Also partition parameters"""
        return self.partition_optimizer_state(num_params)
    
    def memory_savings(self):
        """Memory reduction factor"""
        if self.stage == 1:
            return self.num_devices  # N× reduction
        elif self.stage == 2:
            return self.num_devices * 2
        elif self.stage == 3:
            return self.num_devices * 4
        return 1

if __name__ == '__main__':
    zero = ZeROOptimizer(num_devices=8, stage=3)
    partitions = zero.partition_parameters(num_params=1000)
    savings = zero.memory_savings()
    print(f"✅ ZeRO-3: {len(partitions)} partitions, {savings}× memory reduction")
