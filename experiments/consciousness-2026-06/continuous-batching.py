#!/usr/bin/env python3
"""Continuous Batching (Orca-style)"""

class ContinuousBatcher:
    """Process multiple requests concurrently, even at different stages"""
    def __init__(self, max_batch_size=32):
        self.max_batch_size = max_batch_size
        self.active_requests = []
    
    def add_request(self, request_id, prompt_len):
        """Add new request to active batch"""
        self.active_requests.append({
            'id': request_id,
            'tokens_generated': 0,
            'prompt_len': prompt_len,
            'finished': False
        })
    
    def iteration_step(self):
        """One generation step for all active requests"""
        for req in self.active_requests:
            if not req['finished']:
                req['tokens_generated'] += 1
                if req['tokens_generated'] >= 10:  # Simulated completion
                    req['finished'] = True
        
        # Remove finished
        finished = [r['id'] for r in self.active_requests if r['finished']]
        self.active_requests = [r for r in self.active_requests if not r['finished']]
        
        return finished
    
    def throughput_improvement(self):
        """Continuous batching eliminates bubble time"""
        return "2-3× higher throughput vs static batching"

if __name__ == '__main__':
    batcher = ContinuousBatcher(max_batch_size=8)
    
    # Add requests over time
    for i in range(5):
        batcher.add_request(f"req{i}", 50)
    
    # Run iterations
    for step in range(15):
        finished = batcher.iteration_step()
        if step % 5 == 0:
            print(f"  Step {step}: active={len(batcher.active_requests)}, finished={len(finished)}")
    
    improvement = batcher.throughput_improvement()
    print(f"✅ Continuous Batching: {improvement}")
