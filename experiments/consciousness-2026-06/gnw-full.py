#!/usr/bin/env python3
"""Global Neuronal Workspace (GNW) - Full implementation"""
import numpy as np

class GlobalNeuronalWorkspace:
    def __init__(self, num_modules=8, workspace_threshold=0.7):
        self.modules = {f'mod_{i}': 0.0 for i in range(num_modules)}
        self.workspace_threshold = workspace_threshold
        self.workspace_content = None
        self.broadcast_targets = []
    
    def competition(self):
        """Winner-take-all competition"""
        winner = max(self.modules.items(), key=lambda x: x[1])
        if winner[1] >= self.workspace_threshold:
            self.workspace_content = winner
            return winner
        return None
    
    def broadcast(self):
        """Broadcast to all modules"""
        if self.workspace_content:
            # All modules receive workspace content
            self.broadcast_targets = list(self.modules.keys())
            # Update all modules with workspace info
            for mod in self.modules:
                self.modules[mod] = 0.8 * self.modules[mod] + 0.2 * self.workspace_content[1]
    
    def ignition(self, stimulus, target_module):
        """Sudden increase in activity when stimulus becomes conscious"""
        self.modules[target_module] = stimulus
        winner = self.competition()
        if winner:
            self.broadcast()
            return "conscious"
        return "unconscious"

if __name__ == '__main__':
    gnw = GlobalNeuronalWorkspace(num_modules=8)
    gnw.modules['mod_3'] = 0.85
    result = gnw.ignition(0.85, 'mod_3')
    print(f"✅ GNW (full): {result}, broadcast to {len(gnw.broadcast_targets)} modules")
