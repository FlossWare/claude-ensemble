#!/usr/bin/env python3
"""
Filesystem storage for multi-stage reviews.

Persists review artifacts, requests, worker outputs, and stage results
in a structured directory hierarchy.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from .models import (
    ReviewRequest, ArtifactRef, MultiStageReviewResult, StageReview,
    WorkerOutput, ArbiterOutput, Finding
)

logger = logging.getLogger(__name__)


class ReviewStorage:
    """Manage filesystem storage for review workspaces"""

    def __init__(self, workspace_root: Path):
        """Initialize storage with root directory"""
        self.root = Path(workspace_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_review_workspace(self, request: ReviewRequest) -> Path:
        """Create directory structure for a review"""
        review_dir = self.root / request.id
        review_dir.mkdir(parents=True, exist_ok=True)

        # Save request
        self.save_request(request)

        # Create artifact directory
        artifact_dir = review_dir / "artifact"
        artifact_dir.mkdir(exist_ok=True)

        # Create stages directory
        stages_dir = review_dir / "stages"
        stages_dir.mkdir(exist_ok=True)

        logger.info(f"Created review workspace: {review_dir}")
        return review_dir

    def save_request(self, request: ReviewRequest) -> None:
        """Save review request"""
        review_dir = self.root / request.id
        request_file = review_dir / "request.json"

        with open(request_file, 'w') as f:
            json.dump({
                'id': request.id,
                'artifact_type': request.artifact_type,
                'objective': request.objective,
                'artifacts': [
                    {
                        'location': a.location,
                        'format': a.format,
                        'language': a.language,
                        'size_bytes': a.size_bytes,
                    }
                    for a in request.artifacts
                ],
                'criteria': request.criteria,
                'context': request.context,
                'metadata': request.metadata,
                'timestamp': request.timestamp,
            }, f, indent=2)

        logger.info(f"Saved review request: {request_file}")

    def save_artifact(self, request_id: str, artifact_name: str, content: str) -> None:
        """Save artifact content"""
        artifact_file = self.root / request_id / "artifact" / artifact_name
        artifact_file.parent.mkdir(parents=True, exist_ok=True)

        with open(artifact_file, 'w') as f:
            f.write(content)

        logger.info(f"Saved artifact: {artifact_file}")

    def save_worker_output(self, request_id: str, stage: int, output: WorkerOutput) -> None:
        """Save worker output"""
        stage_dir = self.root / request_id / "stages" / f"{stage:03d}"
        workers_dir = stage_dir / "workers"
        workers_dir.mkdir(parents=True, exist_ok=True)

        worker_file = workers_dir / f"{output.worker_id}.json"

        with open(worker_file, 'w') as f:
            json.dump({
                'worker_id': output.worker_id,
                'model': output.model,
                'stage': output.stage,
                'findings': [f.to_dict() for f in output.findings],
                'summary': output.summary,
                'confidence': output.confidence,
                'duration_ms': output.duration_ms,
                'tokens_used': output.tokens_used,
            }, f, indent=2)

        logger.info(f"Saved worker output: {worker_file}")

    def save_arbiter_output(self, request_id: str, stage: int, output: ArbiterOutput) -> None:
        """Save arbiter output"""
        stage_dir = self.root / request_id / "stages" / f"{stage:03d}"
        arbiter_dir = stage_dir / "arbiter"
        arbiter_dir.mkdir(parents=True, exist_ok=True)

        arbiter_file = arbiter_dir / "output.json"

        with open(arbiter_file, 'w') as f:
            json.dump({
                'arbiter_id': output.arbiter_id,
                'model': output.model,
                'stage': output.stage,
                'findings': [f.to_dict() for f in output.findings],
                'summary': output.summary,
                'contradictions': output.contradictions,
                'unresolved': output.unresolved,
                'confidence': output.confidence,
                'duration_ms': output.duration_ms,
                'tokens_used': output.tokens_used,
            }, f, indent=2)

        logger.info(f"Saved arbiter output: {arbiter_file}")

    def save_stage_review(self, request_id: str, stage_review: StageReview) -> None:
        """Save compiled stage review"""
        stage_dir = self.root / request_id / "stages" / f"{stage_review.stage_number:03d}"
        stage_dir.mkdir(parents=True, exist_ok=True)

        review_file = stage_dir / "review.json"

        with open(review_file, 'w') as f:
            json.dump({
                'stage_number': stage_review.stage_number,
                'findings': [f.to_dict() for f in stage_review.findings],
                'evidence_assessment': stage_review.evidence_assessment,
                'confidence': stage_review.overall_confidence,
                'timestamp': stage_review.timestamp,
            }, f, indent=2)

        logger.info(f"Saved stage review: {review_file}")

    def save_final_result(self, request_id: str, result: MultiStageReviewResult) -> None:
        """Save final multi-stage review result"""
        review_dir = self.root / request_id
        result_file = review_dir / "result.json"

        with open(result_file, 'w') as f:
            f.write(result.to_json())

        logger.info(f"Saved final result: {result_file}")

    def load_request(self, request_id: str) -> ReviewRequest:
        """Load review request"""
        request_file = self.root / request_id / "request.json"

        with open(request_file, 'r') as f:
            data = json.load(f)

        artifacts = [
            ArtifactRef(
                location=a['location'],
                format=a['format'],
                language=a.get('language'),
                size_bytes=a.get('size_bytes', 0),
            )
            for a in data.get('artifacts', [])
        ]

        return ReviewRequest(
            id=data['id'],
            artifact_type=data['artifact_type'],
            objective=data['objective'],
            artifacts=artifacts,
            criteria=data.get('criteria', []),
            context=data.get('context', {}),
            metadata=data.get('metadata', {}),
            timestamp=data['timestamp'],
        )

    def load_artifact(self, request_id: str, artifact_name: str) -> str:
        """Load artifact content"""
        artifact_file = self.root / request_id / "artifact" / artifact_name
        with open(artifact_file, 'r') as f:
            return f.read()

    def load_final_result(self, request_id: str) -> Optional[MultiStageReviewResult]:
        """Load final result if available"""
        result_file = self.root / request_id / "result.json"
        if not result_file.exists():
            return None

        with open(result_file, 'r') as f:
            data = json.load(f)

        # Reconstruct objects from JSON
        request_data = data['request']
        request = ReviewRequest(
            id=request_data['id'],
            artifact_type=request_data['artifact_type'],
            objective=request_data['objective'],
        )

        stages = []
        for stage_data in data.get('stages', []):
            findings = [Finding.from_dict(f) for f in stage_data.get('findings', [])]
            stage = StageReview(
                stage_number=stage_data['stage_number'],
                findings=findings,
                evidence_assessment=stage_data.get('evidence_assessment', {}),
                overall_confidence=stage_data['confidence'],
                timestamp=stage_data['timestamp'],
            )
            stages.append(stage)

        final_findings = [Finding.from_dict(f) for f in data.get('final_findings', [])]

        return MultiStageReviewResult(
            request=request,
            stages=stages,
            final_findings=final_findings,
            consensus_score=data.get('consensus_score', 0.0),
            open_questions=data.get('open_questions', []),
            next_steps=data.get('next_steps', []),
            completed_at=data['completed_at'],
        )

    def log_event(self, request_id: str, event_type: str, details: dict) -> None:
        """Log event to review log"""
        log_file = self.root / request_id / "log.jsonl"

        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'details': details,
        }

        with open(log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')

    def get_review_status(self, request_id: str) -> dict:
        """Get status of a review"""
        review_dir = self.root / request_id

        if not review_dir.exists():
            return {'status': 'not_found'}

        stages_dir = review_dir / "stages"
        completed_stages = 0

        if stages_dir.exists():
            for stage_dir in sorted(stages_dir.iterdir()):
                if (stage_dir / "review.json").exists():
                    completed_stages += 1

        result_file = review_dir / "result.json"
        finished = result_file.exists()

        return {
            'status': 'completed' if finished else 'in_progress',
            'completed_stages': completed_stages,
            'has_result': finished,
        }
