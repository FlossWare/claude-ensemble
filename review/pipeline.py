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

            # Run stage
            stage_review = self.run_stage(
                stage_config,
                artifacts,
                prior_findings,
            )

            self.stage_reviews.append(stage_review)
            prior_findings = stage_review.findings

            logger.info(f"Stage {stage_config.stage_number} complete: {len(stage_review.findings)} findings")

        # Synthesize final result
        result = self.synthesize_result()

        logger.info(f"\n{'='*70}")
        logger.info("REVIEW COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"Total findings: {len(result.final_findings)}")
        logger.info(f"Critical: {len([f for f in result.final_findings if f.severity.value == 'critical'])}")
        logger.info(f"High: {len([f for f in result.final_findings if f.severity.value == 'high'])}")

        return result

    def run_stage(
        self,
        stage_config: StageConfig,
        artifacts: Dict[str, str],
        prior_findings: Optional[List[Finding]],
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
    ) -> List[WorkerOutput]:
        """Execute worker models for a stage"""
        runner = WorkerRunner(self.api_client, self.request, stage_config)

        worker_outputs = runner.run_workers(artifacts, prior_reviews)

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
    ) -> ArbiterOutput:
        """Execute arbiter model for a stage"""
        runner = ArbiterRunner(self.api_client, self.request, stage_config)

        arbiter_output = runner.run_arbiter(artifacts, worker_outputs, prior_findings)

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
