#!/usr/bin/env python3
"""Predictive Processing Framework (full)"""
import numpy as np

class PredictiveProcessing:
    def __init__(self, num_levels=3):
        self.num_levels = num_levels
        self.predictions = [0.0] * num_levels
        self.prediction_errors = [0.0] * num_levels
        self.beliefs = [0.5] * num_levels
        self.precision = [1.0] * num_levels
    
    def predict(self, level):
        """Generate prediction from higher level"""
        if level < self.num_levels - 1:
            self.predictions[level] = self.beliefs[level + 1]
        return self.predictions[level]
    
    def prediction_error(self, level, observation):
        """Calculate weighted prediction error"""
        prediction = self.predict(level)
        error = observation - prediction
        # Weight by precision (inverse variance)
        weighted_error = self.precision[level] * error
        self.prediction_errors[level] = weighted_error
        return weighted_error
    
    def update_beliefs(self, level):
        """Minimize prediction error via belief update"""
        if level < self.num_levels - 1:
            # Update belief to reduce error
            self.beliefs[level] += 0.1 * self.prediction_errors[level]
    
    def process(self, sensory_input):
        """Full predictive processing cycle"""
        # Bottom-up: prediction errors
        self.prediction_error(0, sensory_input)
        
        for level in range(1, self.num_levels):
            self.prediction_error(level, self.beliefs[level-1])
        
        # Top-down: update beliefs
        for level in range(self.num_levels - 1, -1, -1):
            self.update_beliefs(level)

if __name__ == '__main__':
    pp = PredictiveProcessing(num_levels=3)
    pp.process(sensory_input=0.8)
    print(f"✅ Predictive Processing (full): beliefs={pp.beliefs}")
