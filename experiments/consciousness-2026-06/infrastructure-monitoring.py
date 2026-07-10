#!/usr/bin/env python3
"""Infrastructure Monitoring Components"""
import time

# Item 84: Fleet health monitor
class FleetHealthMonitor:
    def __init__(self):
        self.nodes = {}
    
    def check_node(self, node_id):
        """Health check"""
        # Simulate health check
        self.nodes[node_id] = {
            'status': 'healthy',
            'cpu': 45.2,
            'memory': 8192,
            'last_seen': time.time()
        }
        return self.nodes[node_id]

# Item 85: Auto-scaling orchestrator
class AutoScalingOrchestrator:
    def __init__(self, min_nodes=2, max_nodes=10):
        self.min_nodes = min_nodes
        self.max_nodes = max_nodes
        self.current_nodes = min_nodes
    
    def scale_decision(self, load):
        """Decide whether to scale"""
        if load > 0.8 and self.current_nodes < self.max_nodes:
            return 'scale_up'
        elif load < 0.2 and self.current_nodes > self.min_nodes:
            return 'scale_down'
        return 'no_change'

# Item 86: Request batching service
class RequestBatchingService:
    def __init__(self, batch_size=32, timeout_ms=100):
        self.batch_size = batch_size
        self.timeout_ms = timeout_ms
        self.queue = []
    
    def add_request(self, request):
        """Add to batch"""
        self.queue.append(request)
        if len(self.queue) >= self.batch_size:
            return self.flush()
        return None
    
    def flush(self):
        """Return batch"""
        batch = self.queue
        self.queue = []
        return batch

# Item 87: Cache warming system
class CacheWarmingSystem:
    def __init__(self):
        self.cache = {}
        self.popular_items = []
    
    def warm_cache(self, items):
        """Pre-populate cache"""
        for item in items:
            self.cache[item] = f"cached_{item}"
        self.popular_items = items

# Item 88: Rate limiter
class RateLimiter:
    def __init__(self, max_requests=100, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []
    
    def allow_request(self):
        """Check if request allowed"""
        now = time.time()
        # Remove old requests
        self.requests = [r for r in self.requests if now - r < self.window_seconds]
        
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False

if __name__ == '__main__':
    print("✅ Item 84: Fleet Health Monitor")
    monitor = FleetHealthMonitor()
    health = monitor.check_node('server-01')
    print(f"  Status: {health['status']}")
    
    print("✅ Item 85: Auto-Scaling Orchestrator")
    scaler = AutoScalingOrchestrator()
    decision = scaler.scale_decision(load=0.85)
    print(f"  Decision: {decision}")
    
    print("✅ Item 86: Request Batching Service")
    batcher = RequestBatchingService(batch_size=4)
    for i in range(4):
        batch = batcher.add_request(f"req{i}")
    print(f"  Batch size: {len(batch) if batch else 0}")
    
    print("✅ Item 87: Cache Warming System")
    cache = CacheWarmingSystem()
    cache.warm_cache(['item1', 'item2', 'item3'])
    print(f"  Warmed: {len(cache.popular_items)} items")
    
    print("✅ Item 88: Rate Limiter")
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    allowed = sum(1 for _ in range(10) if limiter.allow_request())
    print(f"  Allowed: {allowed}/10 requests")
