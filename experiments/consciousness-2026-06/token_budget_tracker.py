#!/usr/bin/env python3
"""Token Budget Tracker"""

class TokenBudgetTracker:
    def __init__(self, total_budget=200000):
        self.total_budget = total_budget
        self.spent = 0
        self.by_task = {}
    
    def spend(self, task_id, tokens):
        """Record token usage"""
        self.spent += tokens
        self.by_task[task_id] = self.by_task.get(task_id, 0) + tokens
    
    def remaining(self):
        """Tokens left"""
        return max(0, self.total_budget - self.spent)
    
    def can_afford(self, estimated_tokens):
        """Check if within budget"""
        return self.remaining() >= estimated_tokens

if __name__ == '__main__':
    tracker = TokenBudgetTracker(total_budget=200000)
    tracker.spend('task1', 5000)
    tracker.spend('task2', 3000)
    print(f"✅ Token Budget: {tracker.remaining()}/{tracker.total_budget} remaining")
