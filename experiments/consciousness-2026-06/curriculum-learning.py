#!/usr/bin/env python3
"""Curriculum Learning: Easy to hard training"""

class CurriculumLearning:
    def __init__(self, num_epochs=10):
        self.num_epochs = num_epochs
    
    def difficulty_score(self, sample):
        """Assign difficulty (0=easy, 1=hard)"""
        return sample.get('difficulty', 0.5)
    
    def get_curriculum_data(self, data, epoch):
        """Gradually introduce harder samples"""
        difficulty_threshold = epoch / self.num_epochs
        
        filtered = [s for s in data if self.difficulty_score(s) <= difficulty_threshold]
        return filtered if filtered else data

if __name__ == '__main__':
    curriculum = CurriculumLearning(num_epochs=10)
    data = [{'id': i, 'difficulty': i/10} for i in range(10)]
    
    epoch_3_data = curriculum.get_curriculum_data(data, epoch=3)
    print(f"✅ Curriculum Learning: epoch 3 has {len(epoch_3_data)}/10 samples")
