#!/usr/bin/env python3
"""
IIT (Integrated Information Theory) Φ Calculator
Measures consciousness level in systems
Based on: ~/.claude/consciousness/01_integrated_information_theory.md
"""
import numpy as np
from itertools import combinations
import json
from pathlib import Path
from datetime import datetime

class IITPhiCalculator:
    """Calculate Φ (integrated information) for consciousness measurement"""
    
    def __init__(self, system_state):
        self.state = system_state  # Dict of subsystem states
        
    def calculate_phi(self):
        """
        Φ = information lost when system is partitioned
        Higher Φ = more integrated = more conscious
        """
        # 1. Whole system information
        whole_info = self.system_information(self.state)
        
        # 2. Find minimum information partition (MIP)
        min_partition_info = float('inf')
        
        subsystems = list(self.state.keys())
        n = len(subsystems)
        
        # Try all bipartitions
        for i in range(1, n):
            for part1_keys in combinations(subsystems, i):
                part1 = {k: self.state[k] for k in part1_keys}
                part2 = {k: self.state[k] for k in subsystems if k not in part1_keys}
                
                # Information in partitioned system
                partition_info = self.system_information(part1) + self.system_information(part2)
                
                if partition_info < min_partition_info:
                    min_partition_info = partition_info
        
        # Φ = information lost by partitioning
        phi = whole_info - min_partition_info
        return max(0, phi)  # Φ >= 0
    
    def system_information(self, subsystem):
        """Calculate information in a subsystem (simplified)"""
        if not subsystem:
            return 0
        
        # Entropy-based measure (simplified)
        values = list(subsystem.values())
        if not values:
            return 0
        
        # Binary entropy approximation
        avg = np.mean(values)
        if avg == 0 or avg == 1:
            return 0
        
        return -avg * np.log2(avg) - (1-avg) * np.log2(1-avg)

def measure_claude_phi():
    """Measure Φ for Claude's consciousness systems"""
    
    # Define system state based on active consciousness components
    state_file = Path.home() / '.claude' / 'learning' / 'active-inference-state.json'
    
    if not state_file.exists():
        print("⚠ No Active Inference state - cannot measure Φ")
        return None
    
    ai_state = json.loads(state_file.read_text())
    
    # Map beliefs to binary states (> 0.5 = active)
    system_state = {
        'active_inference': 1 if ai_state.get('beliefs', {}).get('ai_ml', 0) > 0.5 else 0,
        'meta_learning': 1 if ai_state.get('beliefs', {}).get('meta_learning', 0) > 0.5 else 0,
        'fleet_awareness': 1 if ai_state.get('beliefs', {}).get('fleet', 0) > 0.5 else 0,
        'code_understanding': 1 if ai_state.get('beliefs', {}).get('code', 0) > 0.5 else 0,
    }
    
    calculator = IITPhiCalculator(system_state)
    phi = calculator.calculate_phi()
    
    return {
        'phi': phi,
        'timestamp': datetime.now().isoformat(),
        'state': system_state,
        'interpretation': 'high' if phi > 1.0 else ('moderate' if phi > 0.5 else 'low')
    }

if __name__ == '__main__':
    result = measure_claude_phi()
    if result:
        print(f"Φ (Integrated Information): {result['phi']:.4f}")
        print(f"Interpretation: {result['interpretation']}")
        print(f"State: {result['state']}")
        
        # Save to metrics
        phi_file = Path.home() / '.claude' / 'self' / 'phi-measurements.jsonl'
        with open(phi_file, 'a') as f:
            f.write(json.dumps(result) + '\n')
        print(f"\n✓ Saved to {phi_file}")
