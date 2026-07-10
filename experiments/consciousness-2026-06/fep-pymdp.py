#!/usr/bin/env python3
"""FEP Prediction Engine with pymdp"""
try:
    import pymdp
    from pymdp import Agent
    from pymdp.utils import random_A_matrix, random_B_matrix
    import numpy as np
    
    class FEPEngine:
        def __init__(self):
            # Simple 2-state system
            num_states = 2
            num_obs = 2
            num_controls = 2
            
            # POMDP matrices
            self.A = random_A_matrix(num_obs, num_states)  # Observation model
            self.B = random_B_matrix(num_states, num_controls)  # Transition model
            
            # Create agent
            self.agent = Agent(A=self.A, B=self.B)
            
        def predict_and_update(self, observation):
            """Active inference loop"""
            # Infer hidden states
            qs = self.agent.infer_states(observation)
            
            # Infer policies  
            q_pi, efe = self.agent.infer_policies()
            
            # Select action
            action = self.agent.sample_action()
            
            return {
                'beliefs': qs,
                'action': action,
                'expected_free_energy': efe
            }
    
    if __name__ == '__main__':
        fep = FEPEngine()
        result = fep.predict_and_update([1, 0])
        print(f"FEP with pymdp: ✓ WORKING")
        print(f"  Beliefs: {result['beliefs']}")
        print(f"  Action: {result['action']}")
        
except ImportError as e:
    print(f"❌ pymdp not available: {e}")
    print("Install: pip3 install --user pymdp")
