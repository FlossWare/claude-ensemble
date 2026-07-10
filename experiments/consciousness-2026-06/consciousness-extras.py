#!/usr/bin/env python3
"""Consciousness Extras: GWT + Recurrent Processing"""

class GlobalWorkspaceTheory:
    """
    GWT: Competition → Broadcast architecture
    From research: winning coalition broadcasts to all modules
    """
    
    def __init__(self, modules):
        self.modules = modules  # Dict of {name: activation}
        self.workspace = None
        self.broadcast_threshold = 0.7
    
    def competition(self):
        """Modules compete for workspace access"""
        # Winner: highest activation
        winner = max(self.modules.items(), key=lambda x: x[1])
        
        if winner[1] >= self.broadcast_threshold:
            self.workspace = winner
            return winner
        return None
    
    def broadcast(self):
        """Winner broadcasts to all modules"""
        if self.workspace:
            winner_name, activation = self.workspace
            # All modules receive broadcast
            for module in self.modules:
                if module != winner_name:
                    # Modulate module activation
                    self.modules[module] = 0.3 * self.modules[module] + 0.7 * activation
            return f"Broadcasting {winner_name} (act={activation:.2f})"
        return "No broadcast (below threshold)"

class RecurrentProcessing:
    """
    Recurrent processing with temporal dynamics
    Iterative refinement over multiple cycles
    """
    
    def __init__(self, state, num_cycles=5):
        self.initial_state = state
        self.state = state
        self.num_cycles = num_cycles
        self.history = [state]
    
    def process(self, feedback_fn):
        """
        Recurrent processing loop
        feedback_fn: function that takes current state, returns refinement
        """
        for cycle in range(self.num_cycles):
            # Get feedback
            refinement = feedback_fn(self.state, cycle)
            
            # Update state (weighted combination)
            self.state = 0.7 * self.state + 0.3 * refinement
            self.history.append(self.state)
        
        return {
            'initial': self.initial_state,
            'final': self.state,
            'convergence': abs(self.state - self.initial_state),
            'cycles': len(self.history)
        }

if __name__ == '__main__':
    # Test GWT
    modules = {'vision': 0.9, 'language': 0.6, 'motor': 0.4, 'memory': 0.5}
    gwt = GlobalWorkspaceTheory(modules)
    
    winner = gwt.competition()
    print(f"GWT Competition: {winner}")
    
    broadcast = gwt.broadcast()
    print(f"GWT Broadcast: {broadcast}")
    print(f"Modules after: {gwt.modules}")
    
    # Test Recurrent
    def feedback(state, cycle):
        # Simulate refinement toward target
        return 0.8 + 0.01 * cycle
    
    rp = RecurrentProcessing(0.5, num_cycles=5)
    result = rp.process(feedback)
    print(f"\nRecurrent Processing:")
    print(f"  Initial: {result['initial']:.3f}")
    print(f"  Final: {result['final']:.3f}")
    print(f"  Convergence: {result['convergence']:.3f}")
    
    print("\n✅ Consciousness extras implemented")
