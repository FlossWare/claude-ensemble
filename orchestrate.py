#!/usr/bin/env python3
"""
Combined review + solve orchestration.

Runs a complete workflow:
1. Multi-stage review to identify problems
2. Multi-stage solve to propose solutions
3. Combined reporting with aggregated totals
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from datetime import datetime

from review.models import ReviewRequest, ArtifactRef
from review.config import ReviewPipelineConfig
from review.pipeline import ReviewPipeline

from solve.models import SolveRequest
from solve.config import SolvePipelineConfig
from solve.pipeline import SolvePipeline


@dataclass
class OrchestrationConfig:
    """Configuration for combined review + solve workflow"""
    review_stages: int = 3
    solve_stages: int = 3
    workers_per_stage: int = 2
    run_solve_after_review: bool = True


class SolveReviewOrchestrator:
    """Orchestrate multi-stage solve followed by multi-stage review

    Flow:
    1. Solve stage(s): Propose solutions to given problems
    2. Review stage(s): Validate and evaluate proposed solutions
    3. Aggregated reporting with combined metrics
    """

    def __init__(self, config: OrchestrationConfig, workspace: Path):
        self.config = config
        self.workspace = Path(workspace)
        self.solve_pipeline: Optional[SolvePipeline] = None
        self.review_pipeline: Optional[ReviewPipeline] = None
        self.start_time = datetime.utcnow()

    def run_review(self, artifact_ref: ArtifactRef, objective: str, criteria: list) -> dict:
        """Run multi-stage review on artifact"""
        request = ReviewRequest(
            artifact_type="code",
            objective=objective,
            artifacts=[artifact_ref],
            criteria=criteria
        )
        config = ReviewPipelineConfig(
            num_stages=self.config.review_stages,
            workers_per_stage=self.config.workers_per_stage
        )
        self.review_pipeline = ReviewPipeline(request, config, self.workspace)
        self.review_pipeline.storage.create_review_workspace(request)

        result = self.review_pipeline.run()
        return {"findings": result, "pipeline": self.review_pipeline}

    def run_solve(self, problems: list, context: str, objective: str) -> dict:
        """Run multi-stage solve on identified problems"""
        request = SolveRequest(
            problems=problems,
            context=context,
            objective=objective
        )
        config = SolvePipelineConfig(
            num_stages=self.config.solve_stages,
            workers_per_stage=self.config.workers_per_stage
        )
        self.solve_pipeline = SolvePipeline(request, config, self.workspace)
        result = self.solve_pipeline.run()
        return {"solutions": result, "pipeline": self.solve_pipeline}

    def generate_combined_report(self) -> str:
        """Generate combined solve + review report with aggregated totals"""
        if not self.solve_pipeline or not self.review_pipeline:
            return "Error: Must run both solve and review before generating report"

        lines = []
        lines.append("")
        lines.append("=" * 150)
        lines.append("COMBINED SOLVE + REVIEW WORKFLOW")
        lines.append("=" * 150)
        lines.append("")

        # Section 1: Solve Report
        lines.append("PHASE 1: MULTI-STAGE SOLVE (Propose Solutions)")
        lines.append("-" * 150)
        lines.append("")
        solve_report = self.solve_pipeline.report_costs()
        lines.extend(solve_report.split('\n')[:30])  # First 30 lines of solve
        lines.append("")

        # Section 2: Review Report
        lines.append("")
        lines.append("PHASE 2: MULTI-STAGE REVIEW (Validate Solutions)")
        lines.append("-" * 150)
        lines.append("")
        review_report = self.review_pipeline.report_costs()
        lines.extend(review_report.split('\n')[:30])  # First 30 lines of review
        lines.append("")

        # Section 3: AGGREGATED TOTALS
        lines.append("")
        lines.append("=" * 150)
        lines.append("AGGREGATED TOTALS (SOLVE + REVIEW)")
        lines.append("=" * 150)
        lines.append("")

        solve_tokens = sum(sc.total_tokens for sc in self.solve_pipeline.stage_costs)
        solve_cost = sum(sc.total_cost for sc in self.solve_pipeline.stage_costs)
        solve_stages = len(self.solve_pipeline.stage_costs)

        review_tokens = sum(sc.total_tokens for sc in self.review_pipeline.stage_costs)
        review_cost = sum(sc.total_cost for sc in self.review_pipeline.stage_costs)
        review_stages = len(self.review_pipeline.stage_costs)

        total_tokens = solve_tokens + review_tokens
        total_cost = solve_cost + review_cost
        total_stages = solve_stages + review_stages

        lines.append("WORKFLOW SUMMARY:")
        lines.append(f"  Solve Stages:         {solve_stages}")
        lines.append(f"  Review Stages:        {review_stages}")
        lines.append(f"  Total Stages:         {total_stages}")
        lines.append("")

        lines.append("COST BREAKDOWN:")
        lines.append(f"  Solve Cost:           ${solve_cost:.4f}")
        lines.append(f"  Review Cost:          ${review_cost:.4f}")
        lines.append(f"  TOTAL COST:           ${total_cost:.4f}")
        lines.append("")

        lines.append("TOKEN BREAKDOWN:")
        lines.append(f"  Solve Tokens:         {solve_tokens:,}")
        lines.append(f"  Review Tokens:        {review_tokens:,}")
        lines.append(f"  TOTAL TOKENS:         {total_tokens:,}")
        lines.append("")

        # Service interaction totals
        solve_memory = sum(sc.memory_recalls for sc in self.solve_pipeline.stage_costs)
        review_memory = sum(sc.memory_recalls for sc in self.review_pipeline.stage_costs)

        solve_thompson = sum(sc.thompson_updates for sc in self.solve_pipeline.stage_costs)
        review_thompson = sum(sc.thompson_updates for sc in self.review_pipeline.stage_costs)

        solve_alerts = sum(sc.alerts_triggered for sc in self.solve_pipeline.stage_costs)
        review_alerts = sum(sc.alerts_triggered for sc in self.review_pipeline.stage_costs)

        lines.append("SERVICE INTERACTIONS:")
        lines.append(f"  Memory Recalls:       {solve_memory + review_memory}")
        lines.append(f"    Solve:              {solve_memory}")
        lines.append(f"    Review:             {review_memory}")
        lines.append(f"  Thompson Updates:     {solve_thompson + review_thompson}")
        lines.append(f"    Solve:              {solve_thompson}")
        lines.append(f"    Review:             {review_thompson}")
        lines.append(f"  Alerts Triggered:     {solve_alerts + review_alerts}")
        lines.append(f"    Solve:              {solve_alerts}")
        lines.append(f"    Review:             {review_alerts}")
        lines.append("")

        # GA Tuning & Autonomous Learning section
        lines.append("GA TUNING & AUTONOMOUS LEARNING:")

        solve_ga_timestamp = None
        review_ga_timestamp = None
        if self.solve_pipeline.stage_costs:
            solve_ga_timestamp = self.solve_pipeline.stage_costs[0].ga_last_evolution_timestamp
        if self.review_pipeline.stage_costs:
            review_ga_timestamp = self.review_pipeline.stage_costs[0].ga_last_evolution_timestamp

        lines.append(f"  Last GA Evolution:    {solve_ga_timestamp or 'Not set (using defaults)'}")
        lines.append("")

        # GA Parameters being used
        if self.solve_pipeline.stage_costs:
            ga = self.solve_pipeline.stage_costs[0]
            lines.append("  GA-Optimized Parameters (Active During Workflow):")
            lines.append(f"    Cache TTL:          {ga.ga_cache_ttl_seconds:.2f} seconds")
            lines.append(f"    Cache Threshold:    {ga.ga_cache_threshold:.2f} ({ga.ga_cache_threshold*100:.0f}% savings required)")
            lines.append(f"    Compression Level:  {ga.ga_compression_level}/9")
            lines.append(f"    Target Reduction:   {ga.ga_target_reduction*100:.1f}%")
            lines.append(f"    Thompson Alpha:     {ga.ga_thompson_alpha:.2f} (prior confidence)")
            lines.append(f"    Thompson Beta:      {ga.ga_thompson_beta:.2f} (prior uncertainty)")
            lines.append("")

        # Autonomous learning updates
        solve_learning = sum(sc.autonomous_learning_updates for sc in self.solve_pipeline.stage_costs)
        review_learning = sum(sc.autonomous_learning_updates for sc in self.review_pipeline.stage_costs)
        total_learning = solve_learning + review_learning

        lines.append(f"  Autonomous Learning Updates: {total_learning}")
        lines.append(f"    During Solve:       {solve_learning} (improved solution proposals)")
        lines.append(f"    During Review:      {review_learning} (improved solution validation)")
        if total_learning > 0:
            lines.append(f"    → Thompson router refined from real task outcomes")
        lines.append("")

        lines.append("EXECUTION TIME:")
        elapsed = datetime.utcnow() - self.start_time
        lines.append(f"  Total Duration:       {elapsed.total_seconds():.2f}s")
        lines.append("")

        lines.append("=" * 150)
        lines.append("END REPORT")
        lines.append("=" * 150)

        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        # Create config
        config = OrchestrationConfig(
            review_stages=2,  # review, meta-review
            solve_stages=2,   # solve, meta-solve
            workers_per_stage=2
        )

        # Create orchestrator
        orchestrator = SolveReviewOrchestrator(config, Path(tmpdir))

        # Define problems to solve
        problems = [
            "SQL Injection vulnerability in authenticate_user",
            "N+1 Query problem in get_user_posts",
            "Missing error handling"
        ]

        # Run solve FIRST - propose solutions
        solve_result = orchestrator.run_solve(
            problems=problems,
            context="Python authentication module",
            objective="Provide secure, performant solutions"
        )

        # Run review SECOND - validate the proposed solutions
        artifact = ArtifactRef(
            location="solutions.txt",
            format="text",
            language="english",
            size_bytes=1000
        )
        artifact._content = "Proposed solutions from solve stage"

        review_result = orchestrator.run_review(
            artifact,
            objective="Validate and evaluate proposed solutions",
            criteria=["feasibility", "security", "performance", "effort"]
        )

        # Generate combined report
        print(orchestrator.generate_combined_report())
