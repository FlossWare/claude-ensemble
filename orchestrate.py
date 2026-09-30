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

from ga_config import DEFAULT_GA_CONFIG


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

    def __init__(self, config: OrchestrationConfig, workspace: Path, api_client=None):
        self.config = config
        self.workspace = Path(workspace)
        self.api_client = api_client
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
        self.review_pipeline = ReviewPipeline(request, config, self.workspace, api_client=self.api_client)
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

        # Calculate all metrics first
        solve_solutions = sum(sc.new_solutions_count for sc in self.solve_pipeline.stage_costs)
        solve_workers = sum(len(sc.worker_decisions) for sc in self.solve_pipeline.stage_costs)
        solve_memory = sum(sc.memory_recalls for sc in self.solve_pipeline.stage_costs)
        solve_thompson = sum(sc.thompson_updates for sc in self.solve_pipeline.stage_costs)

        review_findings = sum(sc.new_findings_count for sc in self.review_pipeline.stage_costs)
        review_workers = sum(len(sc.worker_decisions) for sc in self.review_pipeline.stage_costs)
        review_memory = sum(sc.memory_recalls for sc in self.review_pipeline.stage_costs)
        review_thompson = sum(sc.thompson_updates for sc in self.review_pipeline.stage_costs)

        # Combined metrics table with comprehensive columns
        lines.append("COMBINED WORKFLOW METRICS TABLE:")
        lines.append("")

        w_workflow = 12
        w_stages = 8
        w_workers = 10
        w_tokens = 12
        w_cost = 12
        w_solutions = 12
        w_findings = 12
        w_memory = 8
        w_thompson = 10

        table_width = (w_workflow + w_stages + w_workers + w_tokens + w_cost +
                      w_solutions + w_findings + w_memory + w_thompson + 18)

        header = (f"| {'Workflow':<{w_workflow-2}} " +
                 f"| {'Stages':<{w_stages-2}} " +
                 f"| {'Workers':<{w_workers-2}} " +
                 f"| {'Tokens':<{w_tokens-2}} " +
                 f"| {'Cost':<{w_cost-2}} " +
                 f"| {'Solutions':<{w_solutions-2}} " +
                 f"| {'Findings':<{w_findings-2}} " +
                 f"| {'Memory':<{w_memory-2}} " +
                 f"| {'Thompson':<{w_thompson-2}} |")

        lines.append("=" * table_width)
        lines.append(header)
        lines.append("=" * table_width)

        # Solve row
        solve_row = (f"| {'Solve':<{w_workflow-2}} " +
                    f"| {str(solve_stages):<{w_stages-2}} " +
                    f"| {str(solve_workers):<{w_workers-2}} " +
                    f"| {f'{solve_tokens:,}':<{w_tokens-2}} " +
                    f"| {f'${solve_cost:.4f}':<{w_cost-2}} " +
                    f"| {str(solve_solutions):<{w_solutions-2}} " +
                    f"| {'-':<{w_findings-2}} " +
                    f"| {str(solve_memory):<{w_memory-2}} " +
                    f"| {str(solve_thompson):<{w_thompson-2}} |")
        lines.append(solve_row)
        lines.append("-" * table_width)

        # Review row
        review_row = (f"| {'Review':<{w_workflow-2}} " +
                     f"| {str(review_stages):<{w_stages-2}} " +
                     f"| {str(review_workers):<{w_workers-2}} " +
                     f"| {f'{review_tokens:,}':<{w_tokens-2}} " +
                     f"| {f'${review_cost:.4f}':<{w_cost-2}} " +
                     f"| {'-':<{w_solutions-2}} " +
                     f"| {str(review_findings):<{w_findings-2}} " +
                     f"| {str(review_memory):<{w_memory-2}} " +
                     f"| {str(review_thompson):<{w_thompson-2}} |")
        lines.append(review_row)
        lines.append("-" * table_width)

        # Total row
        total_solutions = solve_solutions
        total_findings = review_findings
        total_workers = solve_workers + review_workers
        total_memory = solve_memory + review_memory
        total_thompson = solve_thompson + review_thompson

        total_row = (f"| {'TOTAL':<{w_workflow-2}} " +
                    f"| {str(total_stages):<{w_stages-2}} " +
                    f"| {str(total_workers):<{w_workers-2}} " +
                    f"| {f'{total_tokens:,}':<{w_tokens-2}} " +
                    f"| {f'${total_cost:.4f}':<{w_cost-2}} " +
                    f"| {str(total_solutions):<{w_solutions-2}} " +
                    f"| {str(total_findings):<{w_findings-2}} " +
                    f"| {str(total_memory):<{w_memory-2}} " +
                    f"| {str(total_thompson):<{w_thompson-2}} |")
        lines.append(total_row)
        lines.append("=" * table_width)
        lines.append("")

        # Service interaction totals
        solve_alerts = sum(sc.alerts_triggered for sc in self.solve_pipeline.stage_costs)
        review_alerts = sum(sc.alerts_triggered for sc in self.review_pipeline.stage_costs)

        solve_knowledge = sum(sc.knowledge_lookups for sc in self.solve_pipeline.stage_costs)
        review_knowledge = sum(sc.knowledge_lookups for sc in self.review_pipeline.stage_costs)

        solve_messages = sum(sc.messages_sent + sc.messages_received for sc in self.solve_pipeline.stage_costs)
        review_messages = sum(sc.messages_sent + sc.messages_received for sc in self.review_pipeline.stage_costs)

        # SERVICE INTERACTIONS TABLE
        lines.append("SERVICE INTERACTIONS TABLE:")
        lines.append("")

        w_service = 18
        w_solve_col = 14
        w_review_col = 14
        w_total_col = 14

        service_table_width = w_service + w_solve_col + w_review_col + w_total_col + 8

        service_header = (f"| {'Service':<{w_service-2}} " +
                         f"| {'Solve':<{w_solve_col-2}} " +
                         f"| {'Review':<{w_review_col-2}} " +
                         f"| {'Total':<{w_total_col-2}} |")

        lines.append("=" * service_table_width)
        lines.append(service_header)
        lines.append("=" * service_table_width)

        services = [
            ("Memory Recalls", solve_memory, review_memory),
            ("Knowledge Lookups", solve_knowledge, review_knowledge),
            ("Messages (Sent+Rcv)", solve_messages, review_messages),
            ("Alerts Triggered", solve_alerts, review_alerts),
            ("Thompson Updates", solve_thompson, review_thompson),
        ]

        for service_name, solve_val, review_val in services:
            total_val = solve_val + review_val
            service_row = (f"| {service_name:<{w_service-2}} " +
                          f"| {str(solve_val):<{w_solve_col-2}} " +
                          f"| {str(review_val):<{w_review_col-2}} " +
                          f"| {str(total_val):<{w_total_col-2}} |")
            lines.append(service_row)
            lines.append("-" * service_table_width)

        # Total row
        total_memory_all = solve_memory + review_memory
        total_knowledge_all = solve_knowledge + review_knowledge
        total_messages_all = solve_messages + review_messages
        total_alerts_all = solve_alerts + review_alerts
        total_thompson_all = solve_thompson + review_thompson

        total_service_row = (f"| {'TOTAL':<{w_service-2}} " +
                            f"| {str(solve_memory + solve_knowledge + solve_messages + solve_alerts + solve_thompson):<{w_solve_col-2}} " +
                            f"| {str(review_memory + review_knowledge + review_messages + review_alerts + review_thompson):<{w_review_col-2}} " +
                            f"| {str(total_memory_all + total_knowledge_all + total_messages_all + total_alerts_all + total_thompson_all):<{w_total_col-2}} |")
        lines.append(total_service_row)
        lines.append("=" * service_table_width)
        lines.append("")

        # GA PARAMETERS TABLE
        lines.append("GA TUNING & AUTONOMOUS LEARNING:")
        lines.append("")

        # Show GA configuration and schedule
        if DEFAULT_GA_CONFIG:
            lines.append(f"GA Tuning Frequency: Every {DEFAULT_GA_CONFIG.format_interval()}")

            solve_ga_timestamp = None
            if self.solve_pipeline.stage_costs:
                solve_ga_timestamp = self.solve_pipeline.stage_costs[0].ga_last_evolution_timestamp

            lines.append(f"Last GA Evolution:   {solve_ga_timestamp or 'Not set (using defaults)'}")
            if solve_ga_timestamp:
                next_run = DEFAULT_GA_CONFIG.next_ga_run_time(solve_ga_timestamp)
                lines.append(f"Next GA Run:         {next_run}")
            lines.append("")

        # GA Parameters table
        if self.solve_pipeline.stage_costs:
            ga = self.solve_pipeline.stage_costs[0]

            w_param = 25
            w_value = 20
            w_description = 40

            ga_table_width = w_param + w_value + w_description + 8

            ga_header = (f"| {'Parameter':<{w_param-2}} " +
                        f"| {'Value':<{w_value-2}} " +
                        f"| {'Description':<{w_description-2}} |")

            lines.append("GA-OPTIMIZED PARAMETERS TABLE:")
            lines.append("")
            lines.append("=" * ga_table_width)
            lines.append(ga_header)
            lines.append("=" * ga_table_width)

            ga_params = [
                ("Cache TTL", f"{ga.ga_cache_ttl_seconds:.2f} sec", "Time-to-live for cached responses"),
                ("Cache Threshold", f"{ga.ga_cache_threshold:.2f} ({ga.ga_cache_threshold*100:.0f}%)", "Savings required to cache"),
                ("Compression Level", f"{ga.ga_compression_level}/9", "ZSTD compression intensity"),
                ("Target Reduction", f"{ga.ga_target_reduction*100:.1f}%", "Target compression ratio"),
                ("Thompson Alpha", f"{ga.ga_thompson_alpha:.2f}", "Prior confidence parameter"),
                ("Thompson Beta", f"{ga.ga_thompson_beta:.2f}", "Prior uncertainty parameter"),
            ]

            for param_name, param_value, param_desc in ga_params:
                ga_row = (f"| {param_name:<{w_param-2}} " +
                         f"| {param_value:<{w_value-2}} " +
                         f"| {param_desc:<{w_description-2}} |")
                lines.append(ga_row)
                lines.append("-" * ga_table_width)

            lines.append("=" * ga_table_width)
            lines.append("")

        # AUTONOMOUS LEARNING TABLE
        solve_learning = sum(sc.autonomous_learning_updates for sc in self.solve_pipeline.stage_costs)
        review_learning = sum(sc.autonomous_learning_updates for sc in self.review_pipeline.stage_costs)
        total_learning = solve_learning + review_learning

        lines.append("AUTONOMOUS LEARNING TABLE:")
        lines.append("")

        w_phase = 20
        w_updates = 12
        w_purpose = 35

        learning_table_width = w_phase + w_updates + w_purpose + 8

        learning_header = (f"| {'Phase':<{w_phase-2}} " +
                          f"| {'Updates':<{w_updates-2}} " +
                          f"| {'Purpose':<{w_purpose-2}} |")

        lines.append("=" * learning_table_width)
        lines.append(learning_header)
        lines.append("=" * learning_table_width)

        learning_phases = [
            ("Solve", str(solve_learning), "Improved solution proposals"),
            ("Review", str(review_learning), "Improved solution validation"),
        ]

        for phase_name, updates_val, purpose_val in learning_phases:
            learning_row = (f"| {phase_name:<{w_phase-2}} " +
                           f"| {updates_val:<{w_updates-2}} " +
                           f"| {purpose_val:<{w_purpose-2}} |")
            lines.append(learning_row)
            lines.append("-" * learning_table_width)

        # Total
        total_learning_row = (f"| {'TOTAL':<{w_phase-2}} " +
                             f"| {str(total_learning):<{w_updates-2}} " +
                             f"| {'Thompson router refinement':<{w_purpose-2}} |")
        lines.append(total_learning_row)
        lines.append("=" * learning_table_width)
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
