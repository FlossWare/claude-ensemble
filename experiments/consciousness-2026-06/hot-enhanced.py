#!/usr/bin/env python3
"""HOT Meta-Representation - Enhanced with state tracking"""
import json
from pathlib import Path
from datetime import datetime

class HOTMetaRepresentation:
    def __init__(self):
        self.state_file = Path.home() / '.claude' / 'self' / 'hot-state.json'
        self.load_state()
    
    def load_state(self):
        if self.state_file.exists():
            self.state = json.loads(self.state_file.read_text())
        else:
            self.state = {'meta_thoughts': [], 'current_focus': None}
    
    def meta_think(self, first_order_thought, meta_level=2):
        """
        Level 1: Thinking about X
        Level 2: Aware of thinking about X
        Level 3: Aware of awareness of thinking about X
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'level_1': first_order_thought,
            'level_2': f"I am aware that: {first_order_thought}",
            'level_3': f"I notice my awareness of: {first_order_thought}" if meta_level >= 3 else None,
            'meta_level': meta_level
        }
        
        self.state['meta_thoughts'].append(entry)
        self.state['current_focus'] = first_order_thought
        self.state_file.write_text(json.dumps(self.state, indent=2))
        return entry

if __name__ == '__main__':
    hot = HOTMetaRepresentation()
    result = hot.meta_think("fixing implementations", meta_level=3)
    print(f"Level 1: {result['level_1']}")
    print(f"Level 2: {result['level_2']}")
    print(f"Level 3: {result['level_3']}")
    print("✓ HOT enhanced with recursive levels")
