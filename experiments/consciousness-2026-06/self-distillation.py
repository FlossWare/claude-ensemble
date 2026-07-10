#!/usr/bin/env python3
"""Self-Distillation: Use model's own predictions as teacher"""
import numpy as np

class SelfDistillation:
    def __init__(self, num_epochs=5):
        self.num_epochs = num_epochs
        self.past_predictions = []
    
    def update_teacher(self, current_predictions):
        """Use past epoch predictions as teacher"""
        self.past_predictions.append(current_predictions.copy())
    
    def get_teacher_target(self):
        """Average of past predictions"""
        if not self.past_predictions:
            return None
        return np.mean(self.past_predictions, axis=0)

if __name__ == '__main__':
    self_distill = SelfDistillation(num_epochs=5)
    
    for epoch in range(3):
        pred = np.random.rand(10, 5)
        self_distill.update_teacher(pred)
    
    teacher = self_distill.get_teacher_target()
    print(f"✅ Self-Distillation: teacher shape {teacher.shape}")
