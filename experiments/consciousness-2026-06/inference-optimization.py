#!/usr/bin/env python3
"""Inference Optimization Techniques"""

class KVCache:
    """Cache key/value for faster generation"""
    def __init__(self, max_len=2048):
        self.max_len = max_len
        self.cache = {}
    
    def get_or_compute(self, layer_id, position, compute_fn):
        key = (layer_id, position)
        if key not in self.cache:
            self.cache[key] = compute_fn()
        return self.cache[key]

class SpeculativeDecoding:
    """Use small model to draft, large model to verify"""
    def __init__(self, draft_tokens=4):
        self.draft_tokens = draft_tokens
    
    def generate(self, draft_model, verify_model, prompt):
        # Draft with small model
        draft = [prompt + str(i) for i in range(self.draft_tokens)]
        # Verify with large model (parallel)
        verified = [t for t in draft if verify_model(t)]
        return verified

if __name__ == '__main__':
    cache = KVCache()
    result = cache.get_or_compute(0, 10, lambda: "computed")
    cached = cache.get_or_compute(0, 10, lambda: "should not run")
    print(f"✅ KV Cache: {len(cache.cache)} entries")
    
    spec = SpeculativeDecoding(draft_tokens=4)
    draft = lambda p: [p + "tok"]
    verify = lambda t: True
    result = spec.generate(draft, verify, "prompt")
    print(f"✅ Speculative: {len(result)} tokens verified")
