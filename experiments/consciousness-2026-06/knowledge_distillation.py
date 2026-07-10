#!/usr/bin/env python3
"""Knowledge Distillation: Train student from teacher"""
import numpy as np

class KnowledgeDistillation:
    def __init__(self, temperature=3.0, alpha=0.5):
        self.temperature = temperature
        self.alpha = alpha
    
    def soft_targets(self, teacher_logits):
        """Soften teacher predictions"""
        scaled = teacher_logits / self.temperature
        return np.exp(scaled) / np.exp(scaled).sum()
    
    def distillation_loss(self, student_logits, teacher_logits, true_labels):
        """Combine soft targets + hard labels"""
        # Soft target loss (KL divergence)
        soft_teacher = self.soft_targets(teacher_logits)
        soft_student = self.soft_targets(student_logits)
        kl_loss = -np.sum(soft_teacher * np.log(soft_student + 1e-8))
        
        # Hard label loss (cross-entropy)
        hard_loss = -np.log(np.exp(student_logits[true_labels]) / np.exp(student_logits).sum() + 1e-8)
        
        # Combine
        total_loss = self.alpha * kl_loss + (1 - self.alpha) * hard_loss
        return total_loss

if __name__ == '__main__':
    kd = KnowledgeDistillation(temperature=3.0, alpha=0.7)
    teacher_logits = np.array([2.0, 1.0, 0.1])
    student_logits = np.array([1.5, 1.2, 0.3])
    loss = kd.distillation_loss(student_logits, teacher_logits, true_labels=0)
    print(f"✅ Knowledge Distillation: loss={loss:.3f}")
