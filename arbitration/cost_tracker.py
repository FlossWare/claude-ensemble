#!/usr/bin/env python3
"""
Cost tracking for multi-phase arbitration reviews.

Writes to THREE locations for maximum utility:
1. Memory Service (semantic search, queryable by tools)
2. Canonical cost_tracking/api_costs.jsonl (dashboards)
3. Project markdown (human-readable, portable)

Full granularity enables future semantic queries:
  "What arbitration tasks cost most?"
  "How has Thompson routing efficiency changed?"
  "Which phases are most expensive?"
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json
import sys
import socket

# Import canonical cost tracking schema
sys.path.insert(0, str(Path(__file__).parent.parent))
from cost_tracking.schema import CostRecord, CANONICAL_LOG_PATH


# Model pricing (tokens per million) and provider registry
MODEL_PRICING = {
    # Anthropic
    'claude-haiku-4-5-20251001': {'input': 0.80, 'output': 2.40, 'provider': 'anthropic'},
    'claude-sonnet-5': {'input': 3.00, 'output': 15.00, 'provider': 'anthropic'},
    'claude-opus-5-5': {'input': 15.00, 'output': 45.00, 'provider': 'anthropic'},

    # Google
    'gemini-2.0-flash': {'input': 0.075, 'output': 0.30, 'provider': 'google'},
    'gemini-2.0-pro': {'input': 0.30, 'output': 1.20, 'provider': 'google'},

    # Other
    'cursor': {'input': 3.00, 'output': 15.00, 'provider': 'jetbrains'},
}

def _get_provider(model: str) -> str:
    """Get provider for model, with explicit registry instead of fragile substring matching."""
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]['provider']
    # Log warning for unknown models instead of silent fallback
    print(f"Warning: Unknown model '{model}', defaulting to 'unknown' provider", file=sys.__stderr__)
    return 'unknown'


@dataclass
class TokenUsage:
    """Token usage for a single API call"""
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def cost(self) -> float:
        """Calculate cost in USD"""
        if self.model not in MODEL_PRICING:
            return 0.0

        pricing = MODEL_PRICING[self.model]
        input_cost = (self.input_tokens / 1_000_000) * pricing['input']
        output_cost = (self.output_tokens / 1_000_000) * pricing['output']
        return input_cost + output_cost

    def __repr__(self) -> str:
        return f"{self.model}: {self.total_tokens:,} tokens (${self.cost():.6f})"


@dataclass
class PhaseMetrics:
    """Metrics for a single arbitration phase"""
    phase: int
    workers: List[str]
    arbiter: str
    worker_usage: List[TokenUsage] = field(default_factory=list)
    arbiter_usage: Optional[TokenUsage] = None

    @property
    def total_tokens(self) -> int:
        total = sum(u.total_tokens for u in self.worker_usage)
        if self.arbiter_usage:
            total += self.arbiter_usage.total_tokens
        return total

    @property
    def total_cost(self) -> float:
        total = sum(u.cost() for u in self.worker_usage)
        if self.arbiter_usage:
            total += self.arbiter_usage.cost()
        return total

    @property
    def worker_count(self) -> int:
        return len(self.workers)

    def get_summary(self) -> Dict:
        """Get summary dict for reporting"""
        return {
            'phase': self.phase,
            'workers': self.workers,
            'arbiter': self.arbiter,
            'total_workers_used': self.worker_count,
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost,
            'cost_per_token': self.total_cost / self.total_tokens if self.total_tokens > 0 else 0,
        }


class CostTracker:
    """Track costs across all phases of arbitration"""

    def __init__(self, task_name: str, task_type: str):
        self.task_name = task_name
        self.task_type = task_type
        self.phases: List[PhaseMetrics] = []
        self.start_time = datetime.utcnow().isoformat()
        self.end_time: Optional[str] = None

    def add_phase(self, phase: int, workers: List[str], arbiter: str) -> PhaseMetrics:
        """Create metrics for a new phase"""
        metrics = PhaseMetrics(phase=phase, workers=workers, arbiter=arbiter)
        self.phases.append(metrics)
        return metrics

    def record_worker_tokens(self, phase: int, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for a worker model"""
        for p in self.phases:
            if p.phase == phase:
                usage = TokenUsage(model=model, input_tokens=input_tokens, output_tokens=output_tokens)
                p.worker_usage.append(usage)
                return

        raise ValueError(f"Phase {phase} not found")

    def record_arbiter_tokens(self, phase: int, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for arbiter model"""
        for p in self.phases:
            if p.phase == phase:
                p.arbiter_usage = TokenUsage(model=model, input_tokens=input_tokens, output_tokens=output_tokens)
                return

        raise ValueError(f"Phase {phase} not found")

    def finish(self) -> None:
        """Mark arbitration as complete"""
        self.end_time = datetime.utcnow().isoformat()

    def write_to_memory_service(self) -> None:
        """Write full-granularity cost data to Memory Service via MemoryClient wrapper."""
        try:
            # Use MemoryClient for REST boundary consistency + error handling
            # (matches pattern of thompson_client, learning_client, etc.)
            sys.path.insert(0, str(Path(__file__).parent.parent / "memory-service"))
            from memory_client import MemoryClient

            content = self._build_memory_document()
            memory_name = f"arbitration_{self.task_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

            client = MemoryClient()
            result = client.write(memory_name, content)

            if not result.get('ok'):
                print(f"Warning: Memory Service write failed: {result.get('error')}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not write to Memory Service: {e}", file=sys.stderr)

    def _build_memory_document(self) -> str:
        """Build detailed arbitration record for semantic indexing."""
        lines = []
        lines.append(f"# Arbitration: {self.task_name}")
        lines.append(f"**Type:** {self.task_type}")
        lines.append(f"**Started:** {self.start_time}")
        lines.append(f"**Completed:** {self.end_time or 'in progress'}")
        lines.append("")

        for phase in self.phases:
            lines.append(f"## Phase {phase.phase}")
            lines.append(f"**Workers:** {', '.join(phase.workers)}")
            lines.append(f"**Arbiter:** {phase.arbiter}")
            lines.append("")

            for usage in phase.worker_usage:
                lines.append(f"- {usage.model}: {usage.total_tokens:,} tokens (${usage.cost():.6f})")

            if phase.arbiter_usage:
                usage = phase.arbiter_usage
                lines.append(f"- {usage.model} (arbiter): {usage.total_tokens:,} tokens (${usage.cost():.6f})")

            lines.append(f"**Phase Total:** {phase.total_tokens:,} tokens, ${phase.total_cost:.6f}")
            lines.append("")

        lines.append("## Summary")
        lines.append(f"**Total Tokens:** {self.total_tokens:,}")
        lines.append(f"**Total Cost:** ${self.total_cost:.6f}")
        lines.append(f"**Cost/Token:** ${self.total_cost / self.total_tokens:.9f}" if self.total_tokens > 0 else "")

        return "\n".join(lines)

    def write_to_canonical_log(self) -> None:
        """Write all costs to canonical cost_tracking/api_costs.jsonl for dashboard integration."""
        try:
            for phase in self.phases:
                # Log worker calls
                for usage in phase.worker_usage:
                    record = CostRecord(
                        timestamp=usage.timestamp,
                        model=usage.model,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        cost_usd=usage.cost(),
                        task_name=self.task_name,
                        source="arbitration",
                        provider=_get_provider(usage.model),
                        metadata={
                            "phase": phase.phase,
                            "role": "worker",
                            "task_type": self.task_type,
                        }
                    )
                    with open(CANONICAL_LOG_PATH, "a") as f:
                        f.write(json.dumps(record.to_dict()) + "\n")

                # Log arbiter call
                if phase.arbiter_usage:
                    usage = phase.arbiter_usage
                    record = CostRecord(
                        timestamp=usage.timestamp,
                        model=usage.model,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        cost_usd=usage.cost(),
                        task_name=self.task_name,
                        source="arbitration",
                        provider=_get_provider(usage.model),
                        metadata={
                            "phase": phase.phase,
                            "role": "arbiter",
                            "task_type": self.task_type,
                        }
                    )
                    with open(CANONICAL_LOG_PATH, "a") as f:
                        f.write(json.dumps(record.to_dict()) + "\n")
        except Exception as e:
            print(f"Warning: Could not write to canonical cost log: {e}", file=sys.stderr)

    @property
    def total_tokens(self) -> int:
        return sum(p.total_tokens for p in self.phases)

    @property
    def total_cost(self) -> float:
        return sum(p.total_cost for p in self.phases)

    @property
    def total_workers(self) -> int:
        return sum(len(p.workers) for p in self.phases)

    @property
    def total_arbiters(self) -> int:
        return len(self.phases)

    def generate_report(self) -> str:
        """Generate detailed cost report"""
        lines = []
        lines.append("=" * 80)
        lines.append("ARBITRATION COST REPORT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Task: {self.task_name}")
        lines.append(f"Type: {self.task_type}")
        lines.append(f"Started: {self.start_time}")
        if self.end_time:
            lines.append(f"Completed: {self.end_time}")
        lines.append("")

        # Per-phase breakdown
        lines.append("-" * 80)
        lines.append("COST BREAKDOWN BY PHASE")
        lines.append("-" * 80)
        lines.append("")

        for phase in self.phases:
            lines.append(f"PHASE {phase.phase}")
            lines.append(f"  Workers: {', '.join(phase.workers)}")
            lines.append(f"  Arbiter: {phase.arbiter}")
            lines.append("")

            # Worker costs
            worker_total = 0.0
            worker_tokens = 0
            if phase.worker_usage:
                lines.append("  Worker Usage:")
                for usage in phase.worker_usage:
                    lines.append(f"    {usage.model:30s} {usage.total_tokens:>8,} tokens  ${usage.cost():>10.6f}")
                    worker_total += usage.cost()
                    worker_tokens += usage.total_tokens
                lines.append(f"    {'Worker Subtotal:':30s} {worker_tokens:>8,} tokens  ${worker_total:>10.6f}")
                lines.append("")

            # Arbiter cost
            arbiter_cost = 0.0
            arbiter_tokens = 0
            if phase.arbiter_usage:
                lines.append("  Arbiter Usage:")
                usage = phase.arbiter_usage
                lines.append(f"    {usage.model:30s} {usage.total_tokens:>8,} tokens  ${usage.cost():>10.6f}")
                arbiter_cost = usage.cost()
                arbiter_tokens = usage.total_tokens
                lines.append("")

            phase_total = worker_total + arbiter_cost
            phase_tokens = worker_tokens + arbiter_tokens
            lines.append(f"  Phase {phase.phase} Total: {phase_tokens:,} tokens, ${phase_total:.6f}")
            lines.append("")

        # Summary
        lines.append("-" * 80)
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append("")
        lines.append(f"Total Phases:        {self.total_arbiters}")
        lines.append(f"Total Workers:       {self.total_workers}")
        lines.append(f"Total Arbiters:      {self.total_arbiters}")
        lines.append(f"Total API Calls:     {self.total_workers + self.total_arbiters}")
        lines.append("")
        lines.append(f"Total Tokens:        {self.total_tokens:,}")
        lines.append(f"Total Cost:          ${self.total_cost:.6f}")
        lines.append(f"Cost/Token:          ${self.total_cost / self.total_tokens:.9f}" if self.total_tokens > 0 else "")
        lines.append(f"Cost/Phase:          ${self.total_cost / self.total_arbiters:.6f}")
        lines.append(f"Cost/Worker:         ${self.total_cost / self.total_workers:.6f}" if self.total_workers > 0 else "")
        lines.append("")

        # Cost by model
        model_costs: Dict[str, Dict] = {}
        for phase in self.phases:
            for usage in phase.worker_usage:
                if usage.model not in model_costs:
                    model_costs[usage.model] = {'tokens': 0, 'cost': 0.0, 'calls': 0}
                model_costs[usage.model]['tokens'] += usage.total_tokens
                model_costs[usage.model]['cost'] += usage.cost()
                model_costs[usage.model]['calls'] += 1

            if phase.arbiter_usage:
                usage = phase.arbiter_usage
                if usage.model not in model_costs:
                    model_costs[usage.model] = {'tokens': 0, 'cost': 0.0, 'calls': 0}
                model_costs[usage.model]['tokens'] += usage.total_tokens
                model_costs[usage.model]['cost'] += usage.cost()
                model_costs[usage.model]['calls'] += 1

        if model_costs:
            lines.append("Cost by Model:")
            for model in sorted(model_costs.keys()):
                stats = model_costs[model]
                lines.append(f"  {model:30s} {stats['calls']:>2} calls  {stats['tokens']:>8,} tokens  ${stats['cost']:>10.6f}")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def to_json(self) -> str:
        """Export as JSON"""
        data = {
            'task_name': self.task_name,
            'task_type': self.task_type,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost,
            'phases': [p.get_summary() for p in self.phases],
        }
        return json.dumps(data, indent=2)
