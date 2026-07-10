#!/usr/bin/env python3
"""Attentional Blink: Temporary blindness after target detection"""

class AttentionalBlink:
    """Simulates attentional blink phenomenon"""
    
    def __init__(self, blink_duration=3):
        self.blink_duration = blink_duration
        self.blink_counter = 0
        self.detected_targets = []
    
    def process_stimulus(self, stimulus, is_target=False):
        """Process stimulus with attentional blink"""
        
        # During blink: reduced detection
        if self.blink_counter > 0:
            detection_prob = 0.2  # Reduced during blink
            self.blink_counter -= 1
        else:
            detection_prob = 0.9  # Normal detection
        
        # Detect target
        if is_target and (hash(str(stimulus)) % 100) < detection_prob * 100:
            self.detected_targets.append(stimulus)
            # Trigger blink
            self.blink_counter = self.blink_duration
            return {'detected': True, 'blink_triggered': True}
        
        return {'detected': False, 'blink_active': self.blink_counter > 0}

if __name__ == '__main__':
    ab = AttentionalBlink()
    # Rapid sequence
    results = []
    for i in range(10):
        result = ab.process_stimulus(f"stim{i}", is_target=(i in [2, 3, 8]))
        results.append(result)
    
    print(f"Detected targets: {len(ab.detected_targets)}/3")
    print("✅ Item 7 complete")
