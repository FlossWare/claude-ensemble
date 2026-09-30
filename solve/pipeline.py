#!/usr/bin/env python3
"""
Multi-stage solution solving pipeline.

Orchestrates workers to propose solutions, arbiters to consolidate,
and meta-stages to challenge and refine those solutions.
"""

from dataclasses import dataclass
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from .models import (
    SolveRequest, SolveResult, SolutionProposal, SolveWorkerOutput,
    SolveArbiterOutput, SolutionStatus, SolutionDisposition
)
from .config import SolvePipelineConfig

logger = logging.getLogger(__name__)


@dataclass
class SolveStageCost:
    """Cost tracking for a single solve stage with solution metrics"""

    def __init__(self, stage_number: int):
        self.stage_number = stage_number
        self.worker_tokens = 0
        self.arbiter_tokens = 0
        self.worker_cost = 0.0
        self.arbiter_cost = 0.0
        self.worker_models = []  # List of (model_name, tokens, cost) tuples
        self.arbiter_model = None  # (model_name, tokens, cost) tuple
        self.cache_hits = 0
        self.cache_misses = 0
        self.compression_ratio = 0.0
        self.input_size_bytes = 0
        self.compressed_size_bytes = 0

        # Service interactions (same as review)
        self.memory_recalls = 0
        self.knowledge_lookups = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.alerts_triggered = 0
        self.graph_queries = 0
        self.arbitration_decisions = 0
        self.thompson_updates = 0
        self.secrets_accessed = 0
        self.mcp_calls = 0
        self.ensemble_routing_hops = 0

        # Thompson sampling
        self.thompson_arm_selected = None
        self.thompson_confidence = 0.0

        # Worker/arbiter decisions on solutions
        self.worker_decisions = []  # List of (worker_id, solution_count, risk_levels)
        self.arbiter_decision = None  # (selected_solution_id, alternatives_count, hybrid)
        self.consensus_percentage = 0.0

        # Solution metrics
        self.prior_solutions_count = 0  # From prior stage
        self.new_solutions_count = 0  # Proposed at this stage
        self.prior_solutions = []  # Actual solutions from prior stage
        self.new_solutions = []  # Solutions proposed at this stage
        self.solutions_evolution = []  # (prior_count, new_count, accepted, rejected, refined)

        # GA tuning
        self.ga_cache_ttl_seconds = 246.87
        self.ga_cache_threshold = 0.44
        self.ga_compression_level = 8
        self.ga_target_reduction = 0.64
        self.ga_thompson_alpha = 2.0
        self.ga_thompson_beta = 5.0
        self.ga_last_evolution_timestamp = None
        self.autonomous_learning_updates = 0

    @property
    def total_tokens(self) -> int:
        return self.worker_tokens + self.arbiter_tokens

    @property
    def total_cost(self) -> float:
        return self.worker_cost + self.arbiter_cost

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0

    def __str__(self) -> str:
        return (f"Solve Stage {self.stage_number}: "
                f"{self.total_tokens:,} tokens, "
                f"${self.total_cost:.4f}, "
                f"{self.new_solutions_count} new solutions")


class SolvePipeline:
    """Orchestrate multi-stage solution solving"""

    def __init__(
        self,
        request: SolveRequest,
        config: SolvePipelineConfig,
        workspace: Path,
        api_client=None,
    ):
        self.request = request
        self.config = config
        self.workspace = Path(workspace)
        self.api_client = api_client
        self.stage_costs: List[SolveStageCost] = []
        self.start_time = datetime.utcnow()

    def run(self) -> SolveResult:
        """Execute multi-stage solving pipeline with real API calls"""
        if not self.api_client:
            raise RuntimeError("API client required for solve execution. Cannot use mock solutions.")

        logger.info(f"Starting {self.config.num_stages}-stage solve for {len(self.request.problems)} problems")

        result = SolveResult(
            request_id=self.request.id,
            num_stages=self.config.num_stages,
            solutions_by_stage={},
        )

        # Initialize stage costs
        for i in range(1, self.config.num_stages + 1):
            self.stage_costs.append(SolveStageCost(i))

        prior_solutions = None

        # Real execution: use workers and arbiters for each stage
        for stage_num, stage_config in enumerate(self.config.stages, 1):
            logger.info(f"Stage {stage_num}: Solving with workers")
            stage_cost = self.stage_costs[stage_num - 1]

            # Import worker/arbiter runners
            from solve.worker_runner import SolveWorkerRunner
            from solve.arbiter_runner import SolveArbiterRunner

            # Run workers to generate solutions
            worker_runner = SolveWorkerRunner(self.api_client, self.request, stage_config)
            worker_outputs = worker_runner.run_workers(self.request.problems, prior_solutions)

            # Track worker costs
            for output in worker_outputs:
                stage_cost.worker_tokens += output.tokens_used
                stage_cost.worker_cost += output.cost_usd
                stage_cost.worker_models.append((output.model, output.tokens_used, output.cost_usd))
                stage_cost.worker_decisions.append((output.worker_id, len(output.solutions), {}))

            # Extract solutions from workers
            all_worker_solutions = []
            for output in worker_outputs:
                if hasattr(output, 'solutions') and output.solutions:
                    all_worker_solutions.extend(output.solutions)

            # Run arbiter to synthesize solutions
            arbiter_runner = SolveArbiterRunner(self.api_client, self.request, stage_config)
            arbiter_output = arbiter_runner.run_arbiter(self.request.problems, worker_outputs, prior_solutions)

            # Track arbiter costs
            stage_cost.arbiter_tokens = arbiter_output.tokens_used
            stage_cost.arbiter_cost = arbiter_output.cost_usd
            stage_cost.arbiter_model = (arbiter_output.model, arbiter_output.tokens_used, arbiter_output.cost_usd)

            # Use arbiter's synthesized solutions
            stage_solutions = arbiter_output.solutions if hasattr(arbiter_output, 'solutions') else all_worker_solutions

            stage_cost.new_solutions = stage_solutions
            stage_cost.new_solutions_count = len(stage_solutions)
            if prior_solutions:
                stage_cost.prior_solutions = prior_solutions
                stage_cost.prior_solutions_count = len(prior_solutions)

            # Store solutions for next stage
            result.solutions_by_stage[stage_num] = stage_solutions
            result.total_cost += stage_cost.total_cost
            result.total_tokens += stage_cost.total_tokens

            prior_solutions = stage_solutions

            logger.info(f"Stage {stage_num} complete: {len(stage_solutions)} solutions, {stage_cost.total_tokens} tokens")

        # Set final solution (highest confidence from last stage)
        if self.stage_costs and self.stage_costs[-1].new_solutions:
            final_stage = self.stage_costs[-1]
            result.final_solution = max(final_stage.new_solutions, key=lambda s: getattr(s, 'confidence', 0.5))

        logger.info(f"Completed {self.config.num_stages}-stage solving with {result.total_tokens} tokens, ${result.total_cost:.4f}")
        return result

    def report_costs(self) -> str:
        """Generate comprehensive solving report with tables"""
        lines = ["", "=" * 150, "SOLVE METRICS: COSTS, TOKENS, SOLUTIONS & ALL SERVICES", "=" * 150, ""]

        # Build metrics table (parallel to review's REVIEW METRICS)
        # Define column widths
        w_stage = 20
        w_models = 45
        w_tokens = 14
        w_cost = 14
        w_solutions = 12
        w_workers = 12

        total_width = (w_stage + w_models + w_tokens + w_cost + w_solutions + w_workers + 12)

        # Header
        header = (f"| {'Stage':<{w_stage-2}} " +
                 f"| {'Models (W→A tok/cost)':<{w_models-2}} " +
                 f"| {'Tokens':<{w_tokens-2}} " +
                 f"| {'Cost':<{w_cost-2}} " +
                 f"| {'Solutions':<{w_solutions-2}} " +
                 f"| {'Workers':<{w_workers-2}} |")

        lines.append("=" * total_width)
        lines.append(header)
        lines.append("=" * total_width)

        # Data rows
        for stage_cost in self.stage_costs:
            if stage_cost.stage_number == 1:
                stage_name = "solve"
            else:
                stage_name = "meta-" * (stage_cost.stage_number - 1) + "solve"

            model_str = "TBD"  # Will be filled in with actual models
            tokens_str = f"{stage_cost.total_tokens:,}"
            cost_str = f"${stage_cost.total_cost:.4f}"
            solutions_str = str(stage_cost.new_solutions_count)
            workers_str = str(len(stage_cost.worker_decisions) if stage_cost.worker_decisions else 0)

            row = (f"| {stage_name:<{w_stage-2}} " +
                   f"| {model_str:<{w_models-2}} " +
                   f"| {tokens_str:<{w_tokens-2}} " +
                   f"| {cost_str:<{w_cost-2}} " +
                   f"| {solutions_str:<{w_solutions-2}} " +
                   f"| {workers_str:<{w_workers-2}} |")
            lines.append(row)
            lines.append("-" * total_width)

        # Totals
        total_tokens = sum(sc.total_tokens for sc in self.stage_costs)
        total_cost = sum(sc.total_cost for sc in self.stage_costs)
        total_solutions = sum(sc.new_solutions_count for sc in self.stage_costs)

        totals = (f"| {'TOTAL':<{w_stage-2}} " +
                 f"| {'':<{w_models-2}} " +
                 f"| {f'{total_tokens:,}':<{w_tokens-2}} " +
                 f"| {f'${total_cost:.4f}':<{w_cost-2}} " +
                 f"| {str(total_solutions):<{w_solutions-2}} " +
                 f"| {'':<{w_workers-2}} |")
        lines.append(totals)
        lines.append("=" * total_width)
        lines.append("")

        # Solutions summary table
        lines.append("=" * 120)
        lines.append("SOLUTIONS SUMMARY TABLE")
        lines.append("=" * 120)
        lines.append("")

        w_stage = 20
        w_inherited = 14
        w_new = 14
        w_total = 10
        w_confidence = 14
        w_cost2 = 14

        table_width = w_stage + w_inherited + w_new + w_total + w_confidence + w_cost2 + 8

        header2 = (f"| {'Stage':<{w_stage-2}} " +
                  f"| {'Inherited':<{w_inherited-2}} " +
                  f"| {'New':<{w_new-2}} " +
                  f"| {'Total':<{w_total-2}} " +
                  f"| {'Avg Confidence':<{w_confidence-2}} " +
                  f"| {'Cost':<{w_cost2-2}} |")

        lines.append("=" * table_width)
        lines.append(header2)
        lines.append("=" * table_width)

        for stage_cost in self.stage_costs:
            if stage_cost.stage_number == 1:
                stage_name = "solve"
            else:
                stage_name = "meta-" * (stage_cost.stage_number - 1) + "solve"

            inherited = stage_cost.prior_solutions_count
            new = stage_cost.new_solutions_count
            total = inherited + new

            avg_confidence = 0.0
            if stage_cost.new_solutions:
                avg_confidence = sum(s.confidence for s in stage_cost.new_solutions) / len(stage_cost.new_solutions)

            row2 = (f"| {stage_name:<{w_stage-2}} " +
                   f"| {str(inherited):<{w_inherited-2}} " +
                   f"| {str(new):<{w_new-2}} " +
                   f"| {str(total):<{w_total-2}} " +
                   f"| {f'{avg_confidence:.0%}':<{w_confidence-2}} " +
                   f"| {f'${stage_cost.total_cost:.4f}':<{w_cost2-2}} |")
            lines.append(row2)
            lines.append("-" * table_width)

        # Totals
        total_inherited = sum(sc.prior_solutions_count for sc in self.stage_costs)
        total_new = sum(sc.new_solutions_count for sc in self.stage_costs)
        total_all = total_inherited + total_new

        totals2 = (f"| {'TOTAL':<{w_stage-2}} " +
                  f"| {str(total_inherited):<{w_inherited-2}} " +
                  f"| {str(total_new):<{w_new-2}} " +
                  f"| {str(total_all):<{w_total-2}} " +
                  f"| {'':<{w_confidence-2}} " +
                  f"| {f'${total_cost:.4f}':<{w_cost2-2}} |")
        lines.append(totals2)
        lines.append("=" * table_width)
        lines.append("")

        # Detailed solutions per stage
        lines.append("=" * 120)
        lines.append("DETAILED SOLUTIONS BY STAGE")
        lines.append("=" * 120)
        lines.append("")

        for stage_cost in self.stage_costs:
            if stage_cost.stage_number == 1:
                stage_name = "solve"
            else:
                stage_name = "meta-" * (stage_cost.stage_number - 1) + "solve"

            lines.append(f"▶ {stage_name.upper()}")
            lines.append("")

            if stage_cost.new_solutions:
                lines.append("  New Solutions Proposed:")
                for sol in stage_cost.new_solutions:
                    lines.append(f"    • {sol.problem_statement[:70]}")
                    lines.append(f"      Confidence: {sol.confidence:.0%} | Risk: {sol.risk_level.value} | Effort: {sol.effort_estimate}")
                lines.append("")

        return "\n".join(lines)
