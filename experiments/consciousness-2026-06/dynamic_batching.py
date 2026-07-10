#!/usr/bin/env python3
"""Dynamic Batching for Inference"""

class DynamicBatcher:
    """Group requests by similar length"""
    def __init__(self, max_batch_size=32, timeout_ms=100):
        self.max_batch_size = max_batch_size
        self.timeout_ms = timeout_ms
        self.queue = []
    
    def add_request(self, request, length):
        """Add request to queue"""
        self.queue.append((request, length))
    
    def form_batch(self):
        """Group by similar lengths"""
        if not self.queue:
            return []
        
        # Sort by length
        sorted_queue = sorted(self.queue, key=lambda x: x[1])
        
        # Take up to max_batch_size with similar lengths
        batch = []
        target_len = sorted_queue[0][1]
        for req, length in sorted_queue:
            if len(batch) >= self.max_batch_size:
                break
            if abs(length - target_len) <= 10:  # Within 10 tokens
                batch.append(req)
        
        # Remove from queue
        self.queue = [x for x in sorted_queue if x[0] not in batch]
        return batch

if __name__ == '__main__':
    batcher = DynamicBatcher(max_batch_size=8)
    for i in range(20):
        batcher.add_request(f"req{i}", 100 + (i % 3) * 10)
    
    batch1 = batcher.form_batch()
    batch2 = batcher.form_batch()
    print(f"✅ Dynamic Batching: batch1={len(batch1)}, batch2={len(batch2)}, remaining={len(batcher.queue)}")
