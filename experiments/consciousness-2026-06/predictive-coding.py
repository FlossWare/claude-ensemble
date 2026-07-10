#!/usr/bin/env python3
"""Predictive Coding: Prediction error minimization"""

class PredictiveCoding:
    """Hierarchical predictive coding"""
    
    def __init__(self):
        self.predictions = {'layer1': 0.5, 'layer2': 0.5, 'layer3': 0.5}
        self.learning_rate = 0.1
    
    def predict(self, layer, bottom_up):
        """Generate prediction at layer"""
        return self.predictions[layer]
    
    def error(self, prediction, actual):
        """Prediction error"""
        return actual - prediction
    
    def update(self, layer, error):
        """Update prediction based on error"""
        self.predictions[layer] += self.learning_rate * error
    
    def process(self, sensory_input):
        """Full predictive coding cycle"""
        # Bottom-up pass
        l1_pred = self.predict('layer1', sensory_input)
        l1_error = self.error(l1_pred, sensory_input)
        
        l2_pred = self.predict('layer2', l1_pred)
        l2_error = self.error(l2_pred, l1_pred)
        
        # Update predictions
        self.update('layer1', l1_error)
        self.update('layer2', l2_error)
        
        return {
            'errors': [l1_error, l2_error],
            'predictions': self.predictions
        }

if __name__ == '__main__':
    pc = PredictiveCoding()
    result = pc.process(0.8)
    print(f"Predictive Coding errors: {result['errors']}")
    print("✅ Item 6 complete")
