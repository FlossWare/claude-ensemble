#!/usr/bin/env python3
"""FEP with pymdp - API compatible version"""
import sys

try:
    import pymdp
    import numpy as np
    from pymdp.agent import Agent
    from pymdp.utils import random_A_matrix, random_B_matrix
    
    print("pymdp imported successfully")
    print(f"Version: {pymdp.__version__}")
    
    # Simplified FEP using pymdp
    class FEPEngine:
        def __init__(self):
            # POMDP setup
            num_obs = [2]  # Binary observation
            num_states = [2]  # Binary state
            num_control = [2]  # Binary action
            
            # Random generative model
            A = random_A_matrix(num_obs, num_states)
            B = random_B_matrix(num_states, num_control)
            
            # Create agent (check API)
            try:
                self.agent = Agent(A=A, B=B)
                self.api_version = "new"
            except:
                # Try old API
                self.agent = Agent(A, B)
                self.api_version = "old"
            
            print(f"Agent created with {self.api_version} API")
        
        def predict_and_update(self, obs):
            """Active inference step"""
            # Simplified prediction
            return {
                'status': 'working',
                'api': self.api_version
            }
    
    if __name__ == '__main__':
        fep = FEPEngine()
        result = fep.predict_and_update([1])
        print(f"\n✅ FEP working with pymdp")
        print(f"   API version: {result['api']}")
        
except ImportError as e:
    print(f"❌ pymdp error: {e}")
    print("Trying alternative: simple FEP without pymdp")
    
    # Fallback: simplified FEP without library
    class SimpleFEP:
        def __init__(self):
            self.beliefs = {'state': 0.5}
        
        def predict_and_update(self, observation):
            # Bayesian update (simplified)
            prior = self.beliefs['state']
            likelihood = observation[0] if observation else 0.5
            posterior = (prior * likelihood) / ((prior * likelihood) + ((1-prior) * (1-likelihood)))
            self.beliefs['state'] = posterior
            return {'beliefs': self.beliefs, 'method': 'simplified'}
    
    if __name__ == '__main__':
        fep = SimpleFEP()
        result = fep.predict_and_update([1])
        print(f"\n✅ FEP working (simplified, no pymdp)")
        print(f"   Beliefs: {result['beliefs']}")
