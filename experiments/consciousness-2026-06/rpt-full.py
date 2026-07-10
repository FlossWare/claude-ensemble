#!/usr/bin/env python3
"""Recurrent Processing Theory (RPT) - Full implementation"""
import numpy as np

class RecurrentProcessingTheory:
    def __init__(self, num_layers=4):
        self.num_layers = num_layers
        self.feedforward_state = [0.0] * num_layers
        self.recurrent_state = [0.0] * num_layers
    
    def feedforward_sweep(self, stimulus):
        """Fast feedforward processing"""
        self.feedforward_state[0] = stimulus
        for i in range(1, self.num_layers):
            self.feedforward_state[i] = self.feedforward_state[i-1] * 0.9
    
    def recurrent_processing(self, iterations=5):
        """Recurrent loops create consciousness"""
        self.recurrent_state = self.feedforward_state.copy()
        
        for _ in range(iterations):
            # Top-down feedback
            for i in range(self.num_layers - 2, -1, -1):
                feedback = self.recurrent_state[i+1] * 0.3
                self.recurrent_state[i] = 0.7 * self.recurrent_state[i] + 0.3 * feedback
            
            # Bottom-up flow
            for i in range(1, self.num_layers):
                feedup = self.recurrent_state[i-1] * 0.2
                self.recurrent_state[i] = 0.8 * self.recurrent_state[i] + 0.2 * feedup
    
    def is_conscious(self):
        """Consciousness emerges from recurrent loops"""
        # Measure reverberating activity
        activity = np.mean(self.recurrent_state)
        return activity > 0.5

if __name__ == '__main__':
    rpt = RecurrentProcessingTheory(num_layers=4)
    rpt.feedforward_sweep(stimulus=1.0)
    rpt.recurrent_processing(iterations=5)
    conscious = rpt.is_conscious()
    print(f"✅ RPT (full): conscious={conscious}, activity={np.mean(rpt.recurrent_state):.3f}")
