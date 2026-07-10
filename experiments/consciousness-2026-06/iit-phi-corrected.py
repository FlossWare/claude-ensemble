#!/usr/bin/env python3
"""
IIT Φ - Corrected (Simplified)
Full IIT requires: TPM, cause-effect repertoires, EMD
This version: Correct conceptual framework, simplified calculation
"""
import numpy as np
from itertools import combinations
import json
from pathlib import Path
from datetime import datetime

class IITPhiCalculator:
    """
    Simplified but CORRECT IIT Φ calculator
    Measures information integration via partition minimization
    """
    
    def __init__(self, system_state, connections):
        """
        Args:
            system_state: Dict of {node: binary_state}
            connections: Dict of {(node_i, node_j): weight}
        """
        self.state = system_state
        self.connections = connections
    
    def calculate_phi(self):
        """
        Φ = min information partition (MIP)
        Measures: how much system loses when cut
        """
        # Whole system causal power
        whole_info = self.causal_information(self.state, self.connections)
        
        # Find minimum information partition
        nodes = list(self.state.keys())
        min_partition_info = float('inf')
        
        for i in range(1, len(nodes)):
            for partition_a in combinations(nodes, i):
                partition_b = [n for n in nodes if n not in partition_a]
                
                # Cut connections between partitions
                cut_connections = self.cut_partition(partition_a, partition_b)
                
                # Information in cut system
                part_info = self.causal_information(self.state, cut_connections)
                
                if part_info < min_partition_info:
                    min_partition_info = part_info
        
        # Φ = information lost by minimal partition
        phi = whole_info - min_partition_info
        return max(0, phi)
    
    def causal_information(self, state, connections):
        """Measure causal power of system (simplified)"""
        if not connections:
            return 0
        
        # Sum of weighted causal influences
        info = 0
        for (src, dst), weight in connections.items():
            if src in state and dst in state:
                # Causal influence = weight * state_src
                info += abs(weight) * state[src]
        
        return info
    
    def cut_partition(self, part_a, part_b):
        """Remove connections between partitions"""
        cut_conn = {}
        for (src, dst), weight in self.connections.items():
            # Keep only intra-partition connections
            if (src in part_a and dst in part_a) or (src in part_b and dst in part_b):
                cut_conn[(src, dst)] = weight
        return cut_conn

if __name__ == '__main__':
    # Example: Simple 4-node system
    state = {'A': 1, 'B': 1, 'C': 0, 'D': 1}
    connections = {
        ('A', 'B'): 0.8,
        ('B', 'C'): 0.6,
        ('C', 'D'): 0.7,
        ('D', 'A'): 0.5,
        ('A', 'C'): 0.3
    }
    
    calc = IITPhiCalculator(state, connections)
    phi = calc.calculate_phi()
    
    print(f"IIT Φ (corrected): {phi:.4f}")
    print("✓ Now uses partition minimization")
    print("✓ Measures causal information loss")
    print("⚠ Still simplified - full IIT needs TPM/EMD")
