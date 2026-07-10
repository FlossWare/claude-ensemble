#!/usr/bin/env python3
"""Working Memory: Limited capacity buffer"""

class WorkingMemory:
    """Limited capacity working memory (Miller's 7±2)"""
    
    def __init__(self, capacity=7):
        self.capacity = capacity
        self.buffer = []
        self.rehearsal_strength = {}
    
    def add(self, item):
        """Add item to working memory"""
        if len(self.buffer) >= self.capacity:
            # Remove weakest item
            weakest = min(self.rehearsal_strength, key=self.rehearsal_strength.get)
            self.buffer.remove(weakest)
            del self.rehearsal_strength[weakest]
        
        self.buffer.append(item)
        self.rehearsal_strength[item] = 1.0
    
    def rehearse(self, item):
        """Rehearse item (strengthens memory)"""
        if item in self.rehearsal_strength:
            self.rehearsal_strength[item] = min(2.0, self.rehearsal_strength[item] + 0.3)
    
    def decay(self):
        """Memory decay over time"""
        for item in list(self.rehearsal_strength.keys()):
            self.rehearsal_strength[item] *= 0.9
            if self.rehearsal_strength[item] < 0.1:
                self.buffer.remove(item)
                del self.rehearsal_strength[item]
    
    def recall(self):
        """Recall current buffer contents"""
        return sorted(self.buffer, key=lambda x: self.rehearsal_strength.get(x, 0), reverse=True)

if __name__ == '__main__':
    wm = WorkingMemory(capacity=7)
    for i in range(10):
        wm.add(f"item{i}")
    print(f"Working Memory: {len(wm.buffer)}/{wm.capacity} items")
    print(f"Items: {wm.recall()}")
    print("✅ Item 8 complete")
