#!/usr/bin/env python3
"""
Claude API Prompt Caching with cache_control

This module implements cache_control integration with the Anthropic Claude API
to reduce costs and latency by caching large static content (memory, documentation,
system prompts) and only processing dynamic user queries.

Reference: https://docs.anthropic.com/en/docs/build-a-system-with-claude/prompt-caching

Key concept: Cacheable content (memory, docs) comes FIRST, user query comes LAST
Structure: [cacheable memory] → [RH docs] → [system prompts] → [user query]
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import anthropic
import os
from datetime import datetime


@dataclass
class CacheMetrics:
    """Track cache performance metrics"""
    request_id: str
    timestamp: datetime
    is_cache_hit: bool
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_without_cache: float
    cost_with_cache: float
    savings: float
    response: str


class PromptCacheControl:
    """
    Manages prompt caching with ephemeral cache_control blocks.

    Usage:
        cache = PromptCacheControl()

        # Structure your messages with cacheable content first
        messages = [
            {"role": "user", "content": "[CACHEABLE MEMORY]\n...large memory..."},
            {"role": "user", "content": "[CACHEABLE DOCS]\n...RH documentation..."},
            {"role": "user", "content": "[SYSTEM PROMPT]\n...system instructions..."},
            {"role": "user", "content": "[USER QUERY]\n...actual question..."},
        ]

        # Mark first 3 messages as cacheable, last one as dynamic
        result = cache.call_with_cache(
            messages=messages,
            cache_eligible_indices=[0, 1, 2],  # First 3 are cacheable
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000
        )
    """

    # Pricing tiers (tokens)
    PRICING = {
        'claude-3-5-sonnet-20241022': {
            'input': 0.003 / 1000,           # $3 per 1M input tokens
            'cache_creation': 0.00375 / 1000, # $3.75 per 1M cache creation tokens (25% premium)
            'cache_read': 0.0003 / 1000,     # $0.30 per 1M cache read tokens (90% discount)
            'output': 0.015 / 1000,          # $15 per 1M output tokens
        },
        'claude-3-5-haiku-20241022': {
            'input': 0.00080 / 1000,         # $0.80 per 1M input tokens
            'cache_creation': 0.001 / 1000,  # $1.00 per 1M cache creation tokens
            'cache_read': 0.00008 / 1000,    # $0.08 per 1M cache read tokens
            'output': 0.004 / 1000,          # $4 per 1M output tokens
        },
        'claude-3-opus-20250219': {
            'input': 0.015 / 1000,           # $15 per 1M input tokens
            'cache_creation': 0.01875 / 1000,# $18.75 per 1M cache creation tokens
            'cache_read': 0.0015 / 1000,     # $1.50 per 1M cache read tokens
            'output': 0.075 / 1000,          # $75 per 1M output tokens
        },
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the cache control handler.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.metrics_history: List[CacheMetrics] = []

    def restructure_prompt(
        self,
        memory: str,
        documentation: str,
        system_prompt: str,
        user_query: str
    ) -> List[Dict[str, str]]:
        """
        Restructure a prompt to place cacheable content first, user query last.

        Structure:
            1. Memory (cacheable)
            2. Documentation (cacheable)
            3. System Prompt (cacheable)
            4. User Query (dynamic, not cached)

        Args:
            memory: Cacheable user memory/context
            documentation: Cacheable documentation (RH docs, etc.)
            system_prompt: Cacheable system instructions
            user_query: The actual user question (dynamic)

        Returns:
            List of message dicts ready for API call
        """
        messages = []

        if memory:
            messages.append({
                "role": "user",
                "content": f"[CACHED MEMORY]\n\n{memory}"
            })

        if documentation:
            messages.append({
                "role": "user",
                "content": f"[CACHED DOCUMENTATION]\n\n{documentation}"
            })

        if system_prompt:
            messages.append({
                "role": "user",
                "content": f"[CACHED SYSTEM PROMPT]\n\n{system_prompt}"
            })

        # User query comes last (NOT cached)
        messages.append({
            "role": "user",
            "content": user_query
        })

        return messages

    def add_cache_control(
        self,
        messages: List[Dict[str, Any]],
        cache_eligible_indices: List[int]
    ) -> List[Dict[str, Any]]:
        """
        Add cache_control ephemeral blocks to eligible messages.

        Args:
            messages: Original message list
            cache_eligible_indices: Indices of messages to cache (0-indexed)

        Returns:
            Messages with cache_control blocks added
        """
        cached_messages = []

        for i, msg in enumerate(messages):
            msg_copy = msg.copy()

            if i in cache_eligible_indices:
                # Add ephemeral cache control to this message
                if "cache_control" not in msg_copy:
                    msg_copy["cache_control"] = {"type": "ephemeral"}
                else:
                    msg_copy["cache_control"]["type"] = "ephemeral"

            cached_messages.append(msg_copy)

        return cached_messages

    def calculate_cost(
        self,
        model: str,
        input_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        output_tokens: int = 0
    ) -> Dict[str, float]:
        """
        Calculate API costs based on token usage.

        Args:
            model: Model name
            input_tokens: Regular input tokens (not cached)
            cache_creation_tokens: Tokens used to create cache
            cache_read_tokens: Tokens read from cache (90% discount)
            output_tokens: Output tokens

        Returns:
            Dict with 'without_cache' and 'with_cache' costs
        """
        pricing = self.PRICING.get(model)
        if not pricing:
            raise ValueError(f"Unknown model: {model}")

        # Cost WITHOUT cache (all tokens at input rate)
        cost_without_cache = (input_tokens + cache_creation_tokens) * pricing['input'] + \
                           output_tokens * pricing['output']

        # Cost WITH cache (cache tokens at discounted rate)
        cost_with_cache = input_tokens * pricing['input'] + \
                        cache_creation_tokens * pricing['cache_creation'] + \
                        cache_read_tokens * pricing['cache_read'] + \
                        output_tokens * pricing['output']

        return {
            'without_cache': cost_without_cache,
            'with_cache': cost_with_cache,
            'savings': cost_without_cache - cost_with_cache,
            'savings_pct': (1 - cost_with_cache / cost_without_cache) * 100 if cost_without_cache > 0 else 0
        }

    def call_with_cache(
        self,
        messages: List[Dict[str, str]],
        cache_eligible_indices: List[int],
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None
    ) -> Tuple[str, CacheMetrics]:
        """
        Call Claude API with cache_control on eligible messages.

        Args:
            messages: List of messages (cacheable content FIRST, query LAST)
            cache_eligible_indices: Indices of messages to cache
            model: Model to use
            max_tokens: Maximum output tokens
            system_prompt: Optional system prompt (sent separately, not cached)

        Returns:
            Tuple of (response_text, cache_metrics)
        """
        # Add cache_control to eligible messages
        cached_messages = self.add_cache_control(messages, cache_eligible_indices)

        # Make API call
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=cached_messages
        )

        # Extract metrics from response
        usage = response.usage
        is_cache_hit = (usage.cache_read_input_tokens > 0)

        # Calculate costs
        cost_data = self.calculate_cost(
            model=model,
            input_tokens=usage.input_tokens,
            cache_creation_tokens=getattr(usage, 'cache_creation_input_tokens', 0),
            cache_read_tokens=getattr(usage, 'cache_read_input_tokens', 0),
            output_tokens=usage.output_tokens
        )

        # Create metrics
        metrics = CacheMetrics(
            request_id=response.id,
            timestamp=datetime.now(),
            is_cache_hit=is_cache_hit,
            input_tokens=usage.input_tokens,
            cache_creation_input_tokens=getattr(usage, 'cache_creation_input_tokens', 0),
            cache_read_input_tokens=getattr(usage, 'cache_read_input_tokens', 0),
            output_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + getattr(usage, 'cache_read_input_tokens', 0) + usage.output_tokens,
            cost_without_cache=cost_data['without_cache'],
            cost_with_cache=cost_data['with_cache'],
            savings=cost_data['savings'],
            response=response.content[0].text
        )

        self.metrics_history.append(metrics)
        return metrics.response, metrics

    def print_metrics(self, metrics: CacheMetrics):
        """Pretty-print cache metrics"""
        print(f"\n{'='*70}")
        print(f"Cache Metrics")
        print(f"{'='*70}")
        print(f"Request ID: {metrics.request_id}")
        print(f"Timestamp: {metrics.timestamp.isoformat()}")
        print(f"Cache Hit: {'✓ YES' if metrics.is_cache_hit else '✗ NO'}")
        print(f"\nToken Usage:")
        print(f"  Regular input tokens: {metrics.input_tokens:,}")
        print(f"  Cache creation tokens: {metrics.cache_creation_input_tokens:,}")
        print(f"  Cache read tokens: {metrics.cache_read_input_tokens:,}")
        print(f"  Output tokens: {metrics.output_tokens:,}")
        print(f"  Total: {metrics.total_tokens:,}")
        print(f"\nCost Analysis:")
        print(f"  Without cache: ${metrics.cost_without_cache:.6f}")
        print(f"  With cache: ${metrics.cost_with_cache:.6f}")
        print(f"  Savings: ${metrics.savings:.6f} ({(metrics.savings/metrics.cost_without_cache*100):.1f}%)")
        print(f"{'='*70}\n")

    def print_comparison(self, metrics_list: List[CacheMetrics]):
        """Print comparison of multiple requests showing cache hits"""
        print(f"\n{'='*80}")
        print(f"Cache Hit Rate Comparison (Multiple Requests)")
        print(f"{'='*80}")
        print(f"{'Req':<5} {'Cache Hit':<12} {'Tokens':<12} {'Cost':<12} {'Savings':<12}")
        print(f"{'-'*80}")

        total_savings = 0
        for i, m in enumerate(metrics_list, 1):
            hit_status = "✓ HIT" if m.is_cache_hit else "✗ MISS"
            tokens = f"{m.total_tokens:,}"
            cost = f"${m.cost_with_cache:.6f}"
            savings = f"${m.savings:.6f}"
            total_savings += m.savings
            print(f"{i:<5} {hit_status:<12} {tokens:<12} {cost:<12} {savings:<12}")

        print(f"{'-'*80}")
        avg_savings = total_savings / len(metrics_list) if metrics_list else 0
        print(f"Average savings per request: ${avg_savings:.6f}")
        print(f"Total savings across {len(metrics_list)} requests: ${total_savings:.6f}")
        print(f"{'='*80}\n")


def restructure_prompt_decorator(
    cache_eligible_blocks: List[int]
) -> callable:
    """
    Decorator to automatically apply cache_control to a function's messages.

    Usage:
        @restructure_prompt_decorator(cache_eligible_blocks=[0, 1, 2])
        def my_api_call(messages, model="claude-3-5-sonnet-20241022"):
            # Function body
            pass

    Args:
        cache_eligible_blocks: Indices of messages to mark as cacheable

    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, messages=None, **kwargs):
            if messages:
                cache = PromptCacheControl()
                messages = cache.add_cache_control(messages, cache_eligible_blocks)
            return func(*args, messages=messages, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    print("Cache Control module loaded. Use PromptCacheControl() to initialize.")
