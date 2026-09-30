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


class ReviewSolveOrchestrator:
    """Orchestrate multi-stage review followed by multi-stage solve"""

    def __init__(self, config: OrchestrationConfig, workspace: Path):
        self.config = config
        self.workspace = Path(workspace)
        self.review_pipeline: Optional[ReviewPipeline] = None
        self.solve_pipeline: Optional[SolvePipeline] = None
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
        """Generate combined review + solve report with aggregated totals"""
        if not self.review_pipeline or not self.solve_pipeline:
            return "Error: Must run both review and solve before generating report"

        lines = []
        lines.append("")
        lines.append("=" * 150)
        lines.append("COMBINED REVIEW + SOLVE WORKFLOW")
        lines.append("=" * 150)
        lines.append("")

        # Section 1: Review Report
        lines.append("PHASE 1: MULTI-STAGE REVIEW")
        lines.append("-" * 150)
        lines.append("")
        review_report = self.review_pipeline.report_costs()
        lines.extend(review_report.split('\n')[:30])  # First 30 lines of review
        lines.append("")

        # Section 2: Solve Report
        lines.append("")
        lines.append("PHASE 2: MULTI-STAGE SOLVE")
        lines.append("-" * 150)
        lines.append("")
        solve_report = self.solve_pipeline.report_costs()
        lines.extend(solve_report.split('\n')[:30])  # First 30 lines of solve
        lines.append("")

        # Section 3: AGGREGATED TOTALS
        lines.append("")
        lines.append("=" * 150)
        lines.append("AGGREGATED TOTALS (REVIEW + SOLVE)")
        lines.append("=" * 150)
        lines.append("")

        review_tokens = sum(sc.total_tokens for sc in self.review_pipeline.stage_costs)
        review_cost = sum(sc.total_cost for sc in self.review_pipeline.stage_costs)
        review_stages = len(self.review_pipeline.stage_costs)

        solve_tokens = sum(sc.total_tokens for sc in self.solve_pipeline.stage_costs)
        solve_cost = sum(sc.total_cost for sc in self.solve_pipeline.stage_costs)
        solve_stages = len(self.solve_pipeline.stage_costs)

        total_tokens = review_tokens + solve_tokens
        total_cost = review_cost + solve_cost
        total_stages = review_stages + solve_stages

        lines.append("WORKFLOW SUMMARY:")
        lines.append(f"  Review Stages:        {review_stages}")
        lines.append(f"  Solve Stages:         {solve_stages}")
        lines.append(f"  Total Stages:         {total_stages}")
        lines.append("")

        lines.append("COST BREAKDOWN:")
        lines.append(f"  Review Cost:          ${review_cost:.4f}")
        lines.append(f"  Solve Cost:           ${solve_cost:.4f}")
        lines.append(f"  TOTAL COST:           ${total_cost:.4f}")
        lines.append("")

        lines.append("TOKEN BREAKDOWN:")
        lines.append(f"  Review Tokens:        {review_tokens:,}")
        lines.append(f"  Solve Tokens:         {solve_tokens:,}")
        lines.append(f"  TOTAL TOKENS:         {total_tokens:,}")
        lines.append("")

        # Service interaction totals
        review_memory = sum(sc.memory_recalls for sc in self.review_pipeline.stage_costs)
        solve_memory = sum(sc.memory_recalls for sc in self.solve_pipeline.stage_costs)

        review_thompson = sum(sc.thompson_updates for sc in self.review_pipeline.stage_costs)
        solve_thompson = sum(sc.thompson_updates for sc in self.solve_pipeline.stage_costs)

        lines.append("SERVICE INTERACTIONS:")
        lines.append(f"  Memory Recalls:       {review_memory + solve_memory}")
        lines.append(f"    Review:             {review_memory}")
        lines.append(f"    Solve:              {solve_memory}")
        lines.append(f"  Thompson Updates:     {review_thompson + solve_thompson}")
        lines.append(f"    Review:             {review_thompson}")
        lines.append(f"    Solve:              {solve_thompson}")
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
        orchestrator = ReviewSolveOrchestrator(config, Path(tmpdir))

        # Run review
        artifact = ArtifactRef(
            location="app.py",
            format="python",
            language="python",
            size_bytes=1000
        )
        artifact._content = "def test(): pass"

        review_result = orchestrator.run_review(
            artifact,
            objective="Security and performance review",
            criteria=["security", "performance"]
        )

        # Extract problems from review findings (in real scenario)
        problems = [
            "SQL Injection vulnerability",
            "N+1 Query problem",
            "Missing error handling"
        ]

        # Run solve
        solve_result = orchestrator.run_solve(
            problems=problems,
            context="Python authentication module",
            objective="Provide secure, performant solutions"
        )

        # Generate combined report
        print(orchestrator.generate_combined_report())
