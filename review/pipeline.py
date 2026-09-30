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
    """Cost tracking for a single stage with optimization, memory and knowledge metrics"""

    def __init__(self, stage_number: int):
        self.stage_number = stage_number
        self.worker_tokens = 0
        self.arbiter_tokens = 0
        self.worker_cost = 0.0
        self.arbiter_cost = 0.0
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

        # Run arbiter
        arbiter_output = self.run_arbiter(
            stage_config,
            artifacts,
            worker_outputs,
            prior_findings,
            stage_cost=stage_cost,
        )

        logger.info(f"Arbiter synthesized: {len(arbiter_output.findings)} findings")

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

        # Track costs
        if stage_cost:
            for output in worker_outputs:
                stage_cost.worker_tokens += output.tokens_used
                stage_cost.worker_cost += output.cost_usd

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

        # Track costs
        if stage_cost:
            stage_cost.arbiter_tokens += arbiter_output.tokens_used
            stage_cost.arbiter_cost += arbiter_output.cost_usd

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
        """Generate comprehensive report: costs, tokens, optimization, memory & knowledge stats"""
        lines = ["", "=" * 100, "COMPREHENSIVE REVIEW REPORT: COSTS, TOKENS, OPTIMIZATION & KNOWLEDGE", "=" * 100, ""]

        total_tokens = 0
        total_cost = 0.0
        total_cache_hits = 0
        total_cache_misses = 0
        total_input_bytes = 0
        total_compressed_bytes = 0
        total_memory_recalls = 0
        total_knowledge_lookups = 0
        total_learning_updates = 0
        total_messages_sent = 0
        total_messages_received = 0
        total_alerts_triggered = 0
        total_graph_queries = 0

        for stage_cost in self.stage_costs:
            stage_name = f"review" if stage_cost.stage_number == 1 else f"meta-" * (stage_cost.stage_number - 1) + "review"

            lines.append(f"\n{stage_name.upper()}:")
            lines.append(f"  ├─ COSTS & TOKENS")
            lines.append(f"  │  ├─ Tokens: {stage_cost.total_tokens:,} (workers: {stage_cost.worker_tokens:,}, arbiter: {stage_cost.arbiter_tokens:,})")
            lines.append(f"  │  └─ Cost:   ${stage_cost.total_cost:.6f} (workers: ${stage_cost.worker_cost:.6f}, arbiter: ${stage_cost.arbiter_cost:.6f})")

            # Caching stats
            if stage_cost.cache_hits or stage_cost.cache_misses:
                total_requests = stage_cost.cache_hits + stage_cost.cache_misses
                lines.append(f"  ├─ CACHING")
                lines.append(f"  │  └─ Hits: {stage_cost.cache_hits}/{total_requests} ({stage_cost.cache_hit_rate:.1f}%)")
                total_cache_hits += stage_cost.cache_hits
                total_cache_misses += stage_cost.cache_misses

            # Compression stats
            if stage_cost.input_size_bytes > 0:
                ratio = (1 - stage_cost.compressed_size_bytes / stage_cost.input_size_bytes) * 100 if stage_cost.compressed_size_bytes <= stage_cost.input_size_bytes else 0
                lines.append(f"  ├─ COMPRESSION")
                lines.append(f"  │  └─ {stage_cost.input_size_bytes:,} → {stage_cost.compressed_size_bytes:,} bytes ({ratio:.1f}% reduction)")
                total_input_bytes += stage_cost.input_size_bytes
                total_compressed_bytes += stage_cost.compressed_size_bytes

            # Services & Knowledge stats
            if (stage_cost.memory_recalls or stage_cost.knowledge_lookups or stage_cost.learning_updates or
                stage_cost.messages_sent or stage_cost.messages_received or stage_cost.alerts_triggered or stage_cost.graph_queries):
                lines.append(f"  └─ SERVICES & KNOWLEDGE")
                if stage_cost.memory_recalls:
                    lines.append(f"     ├─ Memory Service: {stage_cost.memory_recalls} recalls")
                    total_memory_recalls += stage_cost.memory_recalls
                if stage_cost.knowledge_lookups:
                    lines.append(f"     ├─ Knowledge Base: {stage_cost.knowledge_lookups} lookups")
                    total_knowledge_lookups += stage_cost.knowledge_lookups
                if stage_cost.messages_sent or stage_cost.messages_received:
                    lines.append(f"     ├─ Session Messaging: {stage_cost.messages_sent} sent, {stage_cost.messages_received} received")
                    total_messages_sent += stage_cost.messages_sent
                    total_messages_received += stage_cost.messages_received
                if stage_cost.alerts_triggered:
                    lines.append(f"     ├─ Alert Service: {stage_cost.alerts_triggered} triggered")
                    total_messages_sent += stage_cost.alerts_triggered
                if stage_cost.graph_queries:
                    lines.append(f"     ├─ Graph Service: {stage_cost.graph_queries} queries")
                if stage_cost.learning_updates:
                    lines.append(f"     └─ Learning Service: {stage_cost.learning_updates} updates sent")
                    total_learning_updates += stage_cost.learning_updates

            total_tokens += stage_cost.total_tokens
            total_cost += stage_cost.total_cost

        # Totals
        lines.append("\n" + "=" * 100)
        lines.append("TOTALS:")
        lines.append(f"  Tokens: {total_tokens:,} | Cost: ${total_cost:.6f}")

        if total_cache_hits or total_cache_misses:
            total_requests = total_cache_hits + total_cache_misses
            cache_rate = (total_cache_hits / total_requests * 100) if total_requests > 0 else 0
            lines.append(f"  Cache: {total_cache_hits}/{total_requests} hits ({cache_rate:.1f}%)")

        if total_input_bytes > 0:
            total_ratio = (1 - total_compressed_bytes / total_input_bytes) * 100 if total_compressed_bytes <= total_input_bytes else 0
            lines.append(f"  Compression: {total_input_bytes:,} → {total_compressed_bytes:,} bytes ({total_ratio:.1f}% reduction)")

        if any([total_memory_recalls, total_knowledge_lookups, total_learning_updates,
                total_messages_sent, total_messages_received, total_alerts_triggered, total_graph_queries]):
            lines.append(f"  Memory: {total_memory_recalls} recalls | Knowledge: {total_knowledge_lookups} lookups")
            lines.append(f"  Messages: {total_messages_sent} sent / {total_messages_received} received")
            lines.append(f"  Alerts: {total_alerts_triggered} triggered | Graph: {total_graph_queries} queries | Learning: {total_learning_updates} updates")

        lines.append("=" * 100)

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
