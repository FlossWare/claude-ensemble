#!/usr/bin/env python3
"""
Cost Dashboard
Reads cost.log and displays usage in dollars by model, provider, and timeframe.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Tuple

PRICING = {
    'claude-opus-5-5': {'input': 0.015, 'output': 0.045},
    'claude-sonnet-5': {'input': 0.003, 'output': 0.015},
    'claude-haiku-4-5-20251001': {'input': 0.0008, 'output': 0.004},
    'cursor': {'input': 0.003, 'output': 0.015},  # Cursor pricing estimate
    'gemini-2.0-pro': {'input': 0.0015, 'output': 0.006},
    'gemini-2.0-flash': {'input': 0.00005, 'output': 0.00016},
    'gpt-4o': {'input': 0.005, 'output': 0.015},
}


def read_cost_log(log_path: Path) -> List[Dict]:
    """Read JSONL cost log file"""
    entries = []
    if not log_path.exists():
        return entries

    try:
        with open(log_path, 'r') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except Exception as e:
        print(f"Error reading log: {e}", file=sys.stderr)

    return entries


def get_model_price(model: str, token_type: str) -> float:
    """Get price per 1M tokens for model"""
    if model in PRICING:
        return PRICING[model][token_type]

    # Fallback to Sonnet pricing for unknown models
    return PRICING['claude-sonnet-5'][token_type]


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate total cost for a request"""
    input_price = get_model_price(model, 'input')
    output_price = get_model_price(model, 'output')

    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price

    return input_cost + output_cost


def aggregate_by_model(entries: List[Dict]) -> Dict[str, Dict]:
    """Aggregate costs by model"""
    by_model = defaultdict(lambda: {'calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost': 0.0})

    for entry in entries:
        model = entry.get('model', 'unknown')
        input_tokens = entry.get('input_tokens', 0)
        output_tokens = entry.get('output_tokens', 0)

        # Use logged cost if available, else calculate
        cost = entry.get('total_cost_usd') or calculate_cost(model, input_tokens, output_tokens)

        by_model[model]['calls'] += 1
        by_model[model]['input_tokens'] += input_tokens
        by_model[model]['output_tokens'] += output_tokens
        by_model[model]['cost'] += cost

    return dict(by_model)


def aggregate_by_provider(entries: List[Dict]) -> Dict[str, Dict]:
    """Aggregate costs by provider"""
    by_provider = defaultdict(lambda: {'calls': 0, 'cost': 0.0})

    for entry in entries:
        provider = entry.get('provider', 'unknown')
        cost = entry.get('total_cost_usd', 0.0)

        by_provider[provider]['calls'] += 1
        by_provider[provider]['cost'] += cost

    return dict(by_provider)


def aggregate_by_workflow(entries: List[Dict]) -> Dict[str, Dict]:
    """Aggregate costs by workflow"""
    by_workflow = defaultdict(lambda: {'calls': 0, 'cost': 0.0})

    for entry in entries:
        workflow = entry.get('workflow_id', 'default')
        cost = entry.get('total_cost_usd', 0.0)

        by_workflow[workflow]['calls'] += 1
        by_workflow[workflow]['cost'] += cost

    return dict(by_workflow)


def time_bucket(timestamp_str: str, bucket: str = 'daily') -> str:
    """Bucket timestamp into time period"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
    except:
        return 'unknown'

    if bucket == 'hourly':
        return dt.strftime('%Y-%m-%d %H:00')
    elif bucket == 'daily':
        return dt.strftime('%Y-%m-%d')
    elif bucket == 'weekly':
        return dt.strftime('%Y-W%W')
    else:
        return 'unknown'


def aggregate_by_time(entries: List[Dict], bucket: str = 'daily') -> Dict[str, Dict]:
    """Aggregate costs by time bucket"""
    by_time = defaultdict(lambda: {'calls': 0, 'cost': 0.0})

    for entry in entries:
        ts = entry.get('timestamp', '')
        bucket_key = time_bucket(ts, bucket)
        cost = entry.get('total_cost_usd', 0.0)

        by_time[bucket_key]['calls'] += 1
        by_time[bucket_key]['cost'] += cost

    return dict(sorted(by_time.items()))


def print_report(entries: List[Dict]):
    """Print formatted cost report"""
    if not entries:
        print("No cost entries found yet.")
        return

    total_cost = sum(e.get('total_cost_usd', 0.0) for e in entries)
    total_calls = len(entries)

    print("\n" + "="*80)
    print("  COST DASHBOARD")
    print("="*80)
    print(f"\nTotal Cost: ${total_cost:.4f}")
    print(f"Total Calls: {total_calls}")
    print(f"Avg Cost/Call: ${total_cost/total_calls:.6f}" if total_calls else "")

    # By Model
    print("\n" + "-"*80)
    print("COST BY MODEL")
    print("-"*80)
    by_model = aggregate_by_model(entries)
    for model in sorted(by_model.keys()):
        data = by_model[model]
        print(f"{model:40s}  Calls: {data['calls']:4d}  Cost: ${data['cost']:10.4f}")

    # By Provider
    print("\n" + "-"*80)
    print("COST BY PROVIDER")
    print("-"*80)
    by_provider = aggregate_by_provider(entries)
    for provider in sorted(by_provider.keys()):
        data = by_provider[provider]
        print(f"{provider:40s}  Calls: {data['calls']:4d}  Cost: ${data['cost']:10.4f}")

    # By Workflow
    print("\n" + "-"*80)
    print("COST BY WORKFLOW")
    print("-"*80)
    by_workflow = aggregate_by_workflow(entries)
    for workflow in sorted(by_workflow.keys()):
        data = by_workflow[workflow]
        print(f"{workflow:40s}  Calls: {data['calls']:4d}  Cost: ${data['cost']:10.4f}")

    # By Day
    print("\n" + "-"*80)
    print("COST BY DAY")
    print("-"*80)
    by_day = aggregate_by_time(entries, 'daily')
    for day in sorted(by_day.keys()):
        data = by_day[day]
        print(f"{day}  Calls: {data['calls']:4d}  Cost: ${data['cost']:10.4f}")

    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    log_path = Path.home() / '.claude' / 'cost_tracking' / 'cost.log'
    entries = read_cost_log(log_path)
    print_report(entries)
