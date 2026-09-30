#!/usr/bin/env python3
"""
Multi-stage review pipeline orchestration.

Coordinates workers and arbiters across multiple review stages,
ensuring independent re-examination of the original artifact.
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .models import (
    ReviewRequest, ArtifactRef, Finding, WorkerOutput, ArbiterOutput,
    StageReview, MultiStageReviewResult
)
from .config import ReviewPipelineConfig, StageConfig
from .storage import ReviewStorage
from .worker_runner import WorkerRunner
from .arbiter_runner import ArbiterRunner
from .metrics_history import MetricsHistory

logger = logging.getLogger(__name__)

try:
    from learning.learning_client import LearningClient
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False

try:
    from caching.anthropic_api import get_cache_stats
    CACHING_AVAILABLE = True
except ImportError:
    CACHING_AVAILABLE = False

try:
    from compression.compression_service import get_compression_stats
    COMPRESSION_AVAILABLE = True
except ImportError:
    COMPRESSION_AVAILABLE = False


class StageCost:
    """Cost tracking for a single stage with model tracking and optimization metrics"""

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
        self.memory_recalls = 0  # From Memory Service
        self.knowledge_lookups = 0  # From Knowledge Base
        self.learning_updates = 0  # Sent to Thompson
        self.messages_sent = 0  # Via session messaging
        self.messages_received = 0  # Via session messaging
        self.alerts_triggered = 0  # Via Alert Service
        self.graph_queries = 0  # Via Graph Service
        self.arbitration_decisions = 0  # Via Arbitration Orchestrator
        self.thompson_updates = 0  # Via Thompson Service
        self.secrets_accessed = 0  # Via Secrets Service
        self.mcp_calls = 0  # Via MCP servers (code-search, pr-review)
        self.ensemble_routing_hops = 0  # Via Ensemble Server routing
        self.thompson_arm_selected = None  # Thompson sampling arm selected (model/config)
        self.thompson_confidence = 0.0  # Thompson confidence score for selection
        self.thompson_update_priority = 0  # Priority for Thompson learning update
        self.worker_decisions = []  # List of (worker_id, finding_count, severities_summary) tuples
        self.arbiter_decision = None  # (finding_count, confirmed, refuted, modified) tuple
        self.consensus_percentage = 0.0  # % of findings confirmed by arbiter
        self.prior_findings_count = 0  # Number of findings passed from previous stage
        self.prior_findings = []  # Actual findings passed from previous stage (with content)
        self.new_findings_count = 0  # New findings discovered at this stage
        self.new_findings = []  # Actual new findings discovered at this stage
        self.findings_evolution = []  # List of (prior_count, new_count, confirmed, refuted, modified)

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
        return (f"Stage {self.stage_number}: "
                f"{self.total_tokens:,} tokens, "
                f"${self.total_cost:.4f}")


class ReviewPipeline:
    """Orchestrate a multi-stage review"""

    def __init__(
        self,
        request: ReviewRequest,
        config: ReviewPipelineConfig,
        workspace: Path,
        api_client=None,
    ):
        self.request = request
        self.config = config
        self.workspace = Path(workspace)
        self.storage = ReviewStorage(workspace)
        self.api_client = api_client
        self.stage_reviews: List[StageReview] = []
        self.stage_costs: List[StageCost] = []
        self.start_time = datetime.utcnow()

    def validate_request(self) -> bool:
        """Validate review request"""
        if not self.request.objective:
            logger.error("Review objective cannot be empty")
            return False

        if not self.request.artifacts:
            logger.error("No artifacts specified in review request")
            return False

        return True

    def load_artifacts(self) -> Dict[str, str]:
        """Load all artifact content for the review"""
        artifacts = {}

        for artifact in self.request.artifacts:
            # In production, this would read from actual locations (files, URLs, etc.)
            # For now, assume artifact content is provided directly
            if hasattr(artifact, '_content'):
                artifacts[artifact.location] = artifact._content
            else:
                try:
                    artifacts[artifact.location] = self.storage.load_artifact(
                        self.request.id,
                        artifact.location
                    )
                except FileNotFoundError:
                    logger.warning(f"Artifact not found: {artifact.location}")

        return artifacts

    def run(self) -> MultiStageReviewResult:
        """Execute the complete review pipeline"""
        logger.info(f"Starting review pipeline: {self.request.id}")
        logger.info(f"Objective: {self.request.objective}")
        logger.info(f"Stages: {self.config.num_stages}")

        if not self.validate_request():
            raise ValueError("Invalid review request")

        # Load artifacts once
        artifacts = self.load_artifacts()
        if not artifacts:
            raise ValueError("No artifacts available for review")

        logger.info(f"Loaded {len(artifacts)} artifact(s)")

        # Run through stages
        prior_findings: Optional[List[Finding]] = None

        for stage_config in self.config.stages:
            logger.info(f"\n{'='*70}")
            logger.info(f"STAGE {stage_config.stage_number}")
            logger.info(f"{'='*70}")

            # Create cost tracker for this stage
            stage_cost = StageCost(stage_config.stage_number)

            # Run stage
            stage_review = self.run_stage(
                stage_config,
                artifacts,
                prior_findings,
                stage_cost=stage_cost,
            )

            self.stage_reviews.append(stage_review)
            self.stage_costs.append(stage_cost)
            prior_findings = stage_review.findings

            logger.info(f"Stage {stage_config.stage_number} complete: {len(stage_review.findings)} findings")
            logger.info(f"Stage {stage_config.stage_number} cost: {stage_cost}")

        # Synthesize final result
        result = self.synthesize_result()

        # Populate caching and compression stats
        self.populate_optimization_stats()

        # Save metrics to history
        history = MetricsHistory()
        history.save_review_metrics(self.request.id, self.stage_costs, result.consensus_score)

        logger.info(f"\n{'='*70}")
        logger.info("REVIEW COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"Total findings: {len(result.final_findings)}")
        logger.info(f"Critical: {len([f for f in result.final_findings if f.severity.value == 'critical'])}")
        logger.info(f"High: {len([f for f in result.final_findings if f.severity.value == 'high'])}")

        # Send outcome to Learning service for Thompson updates
        if self.config.learning_integration:
            self.send_to_learning(result)

        return result

    def run_stage(
        self,
        stage_config: StageConfig,
        artifacts: Dict[str, str],
        prior_findings: Optional[List[Finding]],
        stage_cost: Optional[StageCost] = None,
    ) -> StageReview:
        """Execute a single stage"""
        # Track context flow
        if stage_cost and prior_findings:
            stage_cost.prior_findings_count = len(prior_findings)
            stage_cost.prior_findings = prior_findings  # Store actual findings

        # Get prior reviews (as context)
        prior_reviews = None
        if self.stage_reviews:
            prior_reviews = self.stage_reviews

        # Run workers independently
        worker_outputs = self.run_workers(
            stage_config,
            artifacts,
            prior_reviews,
            stage_cost=stage_cost,
        )

        logger.info(f"Workers completed: {len(worker_outputs)} outputs")

        # Consolidate worker findings
        consolidated_findings = self.consolidate_findings(worker_outputs)

        # Track new findings (not from prior stage)
        if stage_cost and prior_findings:
            new_count = len(consolidated_findings) - len(prior_findings)
            stage_cost.new_findings_count = max(0, new_count)
            # Store actual new findings
            if new_count > 0:
                prior_ids = {f.id for f in prior_findings}
                stage_cost.new_findings = [f for f in consolidated_findings if f.id not in prior_ids]

        # Run arbiter
        arbiter_output = self.run_arbiter(
            stage_config,
            artifacts,
            worker_outputs,
            prior_findings,
            stage_cost=stage_cost,
        )

        logger.info(f"Arbiter synthesized: {len(arbiter_output.findings)} findings")

        # Record evolution of findings
        if stage_cost and prior_findings and arbiter_output.findings:
            confirmed = sum(1 for f in arbiter_output.findings if f.disposition.value == "confirmed")
            refuted = sum(1 for f in arbiter_output.findings if f.disposition.value == "refuted")
            modified = sum(1 for f in arbiter_output.findings if f.disposition.value == "modified")
            stage_cost.findings_evolution.append((
                stage_cost.prior_findings_count,
                stage_cost.new_findings_count,
                confirmed,
                refuted,
                modified
            ))

        # Compile stage review
        stage_review = StageReview(
            stage_number=stage_config.stage_number,
            workers=worker_outputs,
            arbiter=arbiter_output,
            findings=arbiter_output.findings,
            overall_confidence=arbiter_output.confidence,
        )

        # Save to storage
        self.storage.save_stage_review(self.request.id, stage_review)

        return stage_review

    def run_workers(
        self,
        stage_config: StageConfig,
        artifacts: Dict[str, str],
        prior_reviews: Optional[List[StageReview]],
        stage_cost: Optional[StageCost] = None,
    ) -> List[WorkerOutput]:
        """Execute worker models for a stage"""
        runner = WorkerRunner(self.api_client, self.request, stage_config)

        worker_outputs = runner.run_workers(artifacts, prior_reviews)

        # Track costs, models, and decisions
        if stage_cost:
            for output in worker_outputs:
                stage_cost.worker_tokens += output.tokens_used
                stage_cost.worker_cost += output.cost_usd
                # Track which models were used
                stage_cost.worker_models.append((output.model, output.tokens_used, output.cost_usd))
                # Track worker decisions
                if output.findings:
                    severity_summary = {}
                    for f in output.findings:
                        sev = f.severity.value
                        severity_summary[sev] = severity_summary.get(sev, 0) + 1
                    stage_cost.worker_decisions.append((output.worker_id, len(output.findings), severity_summary))

        # Save worker outputs
        for output in worker_outputs:
            self.storage.save_worker_output(self.request.id, stage_config.stage_number, output)

        return worker_outputs

    def run_arbiter(
        self,
        stage_config: StageConfig,
        artifacts: Dict[str, str],
        worker_outputs: List[WorkerOutput],
        prior_findings: Optional[List[Finding]],
        stage_cost: Optional[StageCost] = None,
    ) -> ArbiterOutput:
        """Execute arbiter model for a stage"""
        runner = ArbiterRunner(self.api_client, self.request, stage_config)

        arbiter_output = runner.run_arbiter(artifacts, worker_outputs, prior_findings)

        # Track costs, models, and decisions
        if stage_cost:
            stage_cost.arbiter_tokens += arbiter_output.tokens_used
            stage_cost.arbiter_cost += arbiter_output.cost_usd
            # Track which arbiter model was used
            stage_cost.arbiter_model = (arbiter_output.model, arbiter_output.tokens_used, arbiter_output.cost_usd)
            # Track arbiter decision
            if arbiter_output.findings:
                confirmed = sum(1 for f in arbiter_output.findings if f.disposition.value == "confirmed")
                refuted = sum(1 for f in arbiter_output.findings if f.disposition.value == "refuted")
                modified = sum(1 for f in arbiter_output.findings if f.disposition.value == "modified")
                stage_cost.arbiter_decision = (len(arbiter_output.findings), confirmed, refuted, modified)
                # Calculate consensus with prior findings
                if prior_findings:
                    stage_cost.consensus_percentage = (confirmed / len(prior_findings) * 100) if prior_findings else 0

        # Save arbiter output
        self.storage.save_arbiter_output(self.request.id, stage_config.stage_number, arbiter_output)

        return arbiter_output

    def consolidate_findings(self, worker_outputs: List[WorkerOutput]) -> List[Finding]:
        """Consolidate duplicate findings from workers"""
        # Simple consolidation: deduplicate similar findings
        all_findings = []
        for output in worker_outputs:
            all_findings.extend(output.findings)

        # For now, return all findings (deduplication would go here)
        return all_findings

    def synthesize_result(self) -> MultiStageReviewResult:
        """Synthesize final result from all stages"""
        # Collect all unique findings with their dispositions
        final_findings = []
        seen_ids = set()

        for stage in self.stage_reviews:
            for finding in stage.findings:
                if finding.id not in seen_ids:
                    final_findings.append(finding)
                    seen_ids.add(finding.id)

        # Calculate consensus score
        consensus = self._calculate_consensus()

        # Generate next steps
        next_steps = self._generate_next_steps(final_findings)

        result = MultiStageReviewResult(
            request=self.request,
            stages=self.stage_reviews,
            final_findings=final_findings,
            consensus_score=consensus,
            next_steps=next_steps,
        )

        # Save final result
        self.storage.save_final_result(self.request.id, result)

        return result

    def _calculate_consensus(self) -> float:
        """Calculate overall consensus score across stages"""
        if not self.stage_reviews:
            return 0.0

        confidence_scores = [s.overall_confidence for s in self.stage_reviews]
        return sum(confidence_scores) / len(confidence_scores)

    def _generate_next_steps(self, findings: List[Finding]) -> List[str]:
        """Generate recommended next steps based on findings"""
        critical = [f for f in findings if f.severity.value == "critical"]
        high = [f for f in findings if f.severity.value == "high"]

        next_steps = []

        if critical:
            next_steps.append(f"Address {len(critical)} critical finding(s) immediately")

        if high:
            next_steps.append(f"Schedule fixes for {len(high)} high-severity findings")

        if len(findings) > 0:
            next_steps.append("Review all findings with team")
            next_steps.append("Update artifact based on recommendations")

        return next_steps

    def report_costs(self) -> str:
        """Generate comprehensive report in table format with all service metrics"""
        lines = ["", "=" * 160, "REVIEW METRICS: COSTS, TOKENS, OPTIMIZATION & ALL SERVICES", "=" * 160, ""]

        # Build table header
        header = "Stage".ljust(15) + "Models (W→A tokens/cost)".ljust(40) + "Tokens".ljust(12) + "Cost".ljust(14) + "Cache%".ljust(10) + "Compress%".ljust(12)
        header += "Memory".ljust(10) + "Knowledge".ljust(12) + "Messages".ljust(12) + "Alerts".ljust(8) + "Graph".ljust(8)
        header += "Arbitration".ljust(12) + "Thompson".ljust(10) + "Secrets".ljust(10) + "MCP".ljust(6) + "Routing".ljust(10)
        lines.append(header)
        lines.append("-" * 200)

        totals = {
            'tokens': 0, 'cost': 0.0, 'cache_hits': 0, 'cache_misses': 0,
            'input_bytes': 0, 'compressed_bytes': 0, 'memory': 0, 'knowledge': 0,
            'messages_sent': 0, 'messages_received': 0, 'alerts': 0, 'graph': 0,
            'arbitration': 0, 'thompson': 0, 'secrets': 0, 'mcp': 0, 'routing': 0
        }

        for stage_cost in self.stage_costs:
            if stage_cost.stage_number == 1:
                stage_name = "review"
            else:
                stage_name = "meta-" * (stage_cost.stage_number - 1) + "review"

            # Build model string with tokens and costs
            model_details = []
            if stage_cost.worker_models:
                for model, tokens, cost in stage_cost.worker_models:
                    model_short = model.split("-")[-1][:6]
                    model_details.append(f"{model_short}({tokens//1000}k/${cost:.2f})")
            worker_str = "+".join(model_details) if model_details else "-"

            if stage_cost.arbiter_model:
                model, tokens, cost = stage_cost.arbiter_model
                model_short = model.split("-")[-1][:6]
                arbiter_str = f"{model_short}({tokens//1000}k/${cost:.2f})"
            else:
                arbiter_str = "-"

            models_str = f"{worker_str}→{arbiter_str}".ljust(40)

            # Tokens and cost
            tokens_str = f"{stage_cost.total_tokens:,}".ljust(12)
            cost_str = f"${stage_cost.total_cost:.4f}".ljust(14)

            # Cache hit rate
            cache_total = stage_cost.cache_hits + stage_cost.cache_misses
            cache_pct = f"{stage_cost.cache_hit_rate:.0f}%" if cache_total > 0 else "-"
            cache_str = cache_pct.ljust(10)

            # Compression ratio
            if stage_cost.input_size_bytes > 0:
                compress_pct = (1 - stage_cost.compressed_size_bytes / stage_cost.input_size_bytes) * 100
                compress_str = f"{compress_pct:.0f}%".ljust(12)
            else:
                compress_str = "-".ljust(12)

            # Service stats
            memory_str = str(stage_cost.memory_recalls).ljust(10)
            knowledge_str = str(stage_cost.knowledge_lookups).ljust(12)
            messages_str = f"{stage_cost.messages_sent}↔{stage_cost.messages_received}".ljust(12)
            alerts_str = str(stage_cost.alerts_triggered).ljust(8)
            graph_str = str(stage_cost.graph_queries).ljust(8)
            arbitration_str = str(stage_cost.arbitration_decisions).ljust(12)

            # Thompson scaling info
            if stage_cost.thompson_arm_selected:
                thompson_str = f"{stage_cost.thompson_arm_selected[:8]}({stage_cost.thompson_confidence:.0%})".ljust(10)
            else:
                thompson_str = str(stage_cost.thompson_updates).ljust(10)

            secrets_str = str(stage_cost.secrets_accessed).ljust(10)
            mcp_str = str(stage_cost.mcp_calls).ljust(6)
            routing_str = str(stage_cost.ensemble_routing_hops).ljust(10)

            row = (stage_name.ljust(15) + models_str + tokens_str + cost_str + cache_str + compress_str +
                   memory_str + knowledge_str + messages_str + alerts_str + graph_str +
                   arbitration_str + thompson_str + secrets_str + mcp_str + routing_str)
            lines.append(row)

            # Accumulate totals
            totals['tokens'] += stage_cost.total_tokens
            totals['cost'] += stage_cost.total_cost
            totals['cache_hits'] += stage_cost.cache_hits
            totals['cache_misses'] += stage_cost.cache_misses
            totals['input_bytes'] += stage_cost.input_size_bytes
            totals['compressed_bytes'] += stage_cost.compressed_size_bytes
            totals['memory'] += stage_cost.memory_recalls
            totals['knowledge'] += stage_cost.knowledge_lookups
            totals['messages_sent'] += stage_cost.messages_sent
            totals['messages_received'] += stage_cost.messages_received
            totals['alerts'] += stage_cost.alerts_triggered
            totals['graph'] += stage_cost.graph_queries
            totals['arbitration'] += stage_cost.arbitration_decisions
            totals['thompson'] += stage_cost.thompson_updates
            totals['secrets'] += stage_cost.secrets_accessed
            totals['mcp'] += stage_cost.mcp_calls
            totals['routing'] += stage_cost.ensemble_routing_hops

        # Total row
        lines.append("-" * 200)
        cache_total = totals['cache_hits'] + totals['cache_misses']
        cache_pct = f"{(totals['cache_hits'] / cache_total * 100):.0f}%" if cache_total > 0 else "-"
        compress_pct_val = (1 - totals['compressed_bytes'] / totals['input_bytes']) * 100 if totals['input_bytes'] > 0 else 0
        compress_str = f"{compress_pct_val:.0f}%" if totals['input_bytes'] > 0 else "-"

        total_row = ("TOTAL".ljust(15) +
                     f"{totals['tokens']:,}".ljust(12) +
                     f"${totals['cost']:.4f}".ljust(14) +
                     cache_pct.ljust(10) +
                     compress_str.ljust(12) +
                     str(totals['memory']).ljust(10) +
                     str(totals['knowledge']).ljust(12) +
                     f"{totals['messages_sent']}↔{totals['messages_received']}".ljust(12) +
                     str(totals['alerts']).ljust(8) +
                     str(totals['graph']).ljust(8) +
                     str(totals['arbitration']).ljust(12) +
                     str(totals['thompson']).ljust(10) +
                     str(totals['secrets']).ljust(10) +
                     str(totals['mcp']).ljust(6) +
                     str(totals['routing']).ljust(10))
        lines.append(total_row)
        lines.append("=" * 200)

        # Add decision summary section
        lines.append("")
        lines.append("=" * 220)
        lines.append("COMPLETE STAGE ANALYSIS: CONTEXT, FINDINGS, DECISIONS & EVOLUTION")
        lines.append("=" * 220)
        lines.append("")

        # Build unified table
        for stage_cost in self.stage_costs:
            if stage_cost.stage_number == 1:
                stage_name = "REVIEW"
            else:
                stage_name = "META-" * (stage_cost.stage_number - 1) + "REVIEW"

            lines.append(f"┌─ {stage_name} {chr(9472) * (210 - len(stage_name) - 4)}")
            lines.append("├─ INHERITED CONTEXT (Prior Stage)")
            if stage_cost.prior_findings:
                for i, finding in enumerate(stage_cost.prior_findings, 1):
                    lines.append(f"│  {i}. [{finding.severity.value.upper():8s}] {finding.subject}")
                    lines.append(f"│     {finding.description[:80]}")
            else:
                lines.append("│  (None - Initial stage)")

            lines.append("│")
            lines.append("├─ NEW DISCOVERIES (This Stage)")
            if stage_cost.new_findings:
                for i, finding in enumerate(stage_cost.new_findings, 1):
                    lines.append(f"│  {i}. [NEW] [{finding.severity.value.upper():8s}] {finding.subject}")
                    lines.append(f"│        {finding.description[:80]}")
            else:
                lines.append("│  (None discovered)")

            lines.append("│")
            lines.append("├─ WORKER FINDINGS & ARBITER DECISION")
            if stage_cost.worker_decisions:
                for worker_id, finding_count, severity_summary in stage_cost.worker_decisions:
                    severity_str = " | ".join([f"{sev}:{count}" for sev, count in sorted(severity_summary.items())])
                    lines.append(f"│  Worker {worker_id}: {finding_count} findings ({severity_str})")
            else:
                lines.append("│  Workers: No findings")

            if stage_cost.arbiter_decision:
                total, confirmed, refuted, modified = stage_cost.arbiter_decision
                lines.append(f"│  Arbiter: {total} findings → {confirmed}✓ {refuted}✗ {modified}◐")
            if stage_cost.consensus_percentage > 0:
                lines.append(f"│  Consensus: {stage_cost.consensus_percentage:.0f}% of prior findings confirmed")

            lines.append("│")
            lines.append("├─ FLOW METRICS")
            prior_count = stage_cost.prior_findings_count
            new_count = stage_cost.new_findings_count
            total_count = prior_count + new_count
            lines.append(f"│  Prior Context: {prior_count:2d} | New Discoveries: {new_count:2d} | Total Evaluated: {total_count:2d}")
            if stage_cost.findings_evolution:
                prior, new, confirmed, refuted, modified = stage_cost.findings_evolution[0]
                lines.append(f"│  Evolution: {confirmed} confirmed, {refuted} refuted, {modified} modified")

            lines.append("└" + chr(9472) * 218)
            lines.append("")

        lines.append("=" * 220)

        return "\n".join(lines)

    def populate_optimization_stats(self) -> None:
        """Populate caching and compression statistics for each stage"""
        if CACHING_AVAILABLE:
            try:
                cache_stats = get_cache_stats()
                for stage_cost in self.stage_costs:
                    if stage_cost.stage_number in cache_stats:
                        stats = cache_stats[stage_cost.stage_number]
                        stage_cost.cache_hits = stats.get('hits', 0)
                        stage_cost.cache_misses = stats.get('misses', 0)
            except Exception as e:
                logger.debug(f"Could not populate caching stats: {e}")

        if COMPRESSION_AVAILABLE:
            try:
                compression_stats = get_compression_stats()
                for stage_cost in self.stage_costs:
                    if stage_cost.stage_number in compression_stats:
                        stats = compression_stats[stage_cost.stage_number]
                        stage_cost.input_size_bytes = stats.get('input_bytes', 0)
                        stage_cost.compressed_size_bytes = stats.get('compressed_bytes', 0)
            except Exception as e:
                logger.debug(f"Could not populate compression stats: {e}")

    def send_to_learning(self, result: MultiStageReviewResult) -> bool:
        """Send review outcome to Learning service for Thompson updates"""
        if not LEARNING_AVAILABLE:
            logger.debug("Learning service not available, skipping outcome recording")
            return False

        try:
            client = LearningClient()
            total_tokens = sum(sc.total_tokens for sc in self.stage_costs)
            total_cost = sum(sc.total_cost for sc in self.stage_costs)

            # Record outcome for consensus score
            task_id = f"review_{self.request.id}_{datetime.utcnow().isoformat()}"
            rating = int(result.consensus_score * 5)  # Convert 0.0-1.0 to 1-5 scale

            client.process_outcome(
                task_id=task_id,
                task_type="multi_stage_review",
                model="multi-stage-arbiter",  # Model is the review system itself
                rating=rating,
                tokens=total_tokens,
                cost=total_cost,
            )

            logger.info(f"Review outcome recorded: {task_id} (consensus: {result.consensus_score:.1%})")
            return True
        except Exception as e:
            logger.warning(f"Failed to send review outcome to Learning service: {e}")
            return False
