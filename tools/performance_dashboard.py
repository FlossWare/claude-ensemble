#!/usr/bin/env python3
"""
Performance Dashboard - Display real cost tracking metrics
Shows Thompson routing performance, cost savings, and model selection
Uses file-based logs (no database needed)
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ANSI colors
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

class PerformanceDashboard:
    def __init__(self, log_file=None, hours=24):
        self.log_file = Path(log_file or 'cost_tracking/api_costs.jsonl')
        self.hours = hours
        self.cutoff = datetime.now() - timedelta(hours=hours)
        self.data = self._load_logs()
    
    def _load_logs(self):
        """Load API cost logs from JSONL file"""
        data = []
        if not self.log_file.exists():
            return data

        try:
            with open(self.log_file) as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        # Parse timestamp if present
                        if 'timestamp' in record:
                            ts = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                            if ts.replace(tzinfo=None) >= self.cutoff:
                                data.append(record)
                        else:
                            data.append(record)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass

        return data
    
    def display(self):
        """Display dashboard"""
        if not self.data:
            print(f"{YELLOW}No data in last {self.hours} hours{RESET}")
            return
        
        # Aggregate by model
        by_model = defaultdict(lambda: {'count': 0, 'cost': 0.0, 'tokens': 0})
        for record in self.data:
            model = record.get('model', 'unknown')
            by_model[model]['count'] += 1
            by_model[model]['cost'] += record.get('cost', 0)
            by_model[model]['tokens'] += record.get('prompt_tokens', 0) + record.get('completion_tokens', 0)
        
        # Display
        print(f"\n{BOLD}╔{'='*60}╗{RESET}")
        print(f"{BOLD}║  PERFORMANCE DASHBOARD - RH Tools{' '*26}║{RESET}")
        print(f"{BOLD}╚{'='*60}╝{RESET}")
        
        print(f"\n{BOLD}Total API Calls:{RESET} {GREEN}{len(self.data)}{RESET}")
        print(f"{BOLD}Total Cost:{RESET} {GREEN}${sum(r.get('cost', 0) for r in self.data):.2f}{RESET}")
        print(f"{BOLD}Total Tokens:{RESET} {GREEN}{sum(r.get('prompt_tokens', 0) + r.get('completion_tokens', 0) for r in self.data):,}{RESET}")
        
        print(f"\n{BOLD}By Model:{RESET}")
        for model in sorted(by_model.keys()):
            stats = by_model[model]
            print(f"  {model:20s}: {stats['count']:3d} calls | ${stats['cost']:7.2f} | {stats['tokens']:,} tokens")
        
        print(f"\n{BOLD}Data source:{RESET} {self.log_file}")
        print(f"{BOLD}Time range:{RESET} Last {self.hours} hours\n")

if __name__ == '__main__':
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    dashboard = PerformanceDashboard(hours=hours)
    dashboard.display()
