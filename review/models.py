#!/usr/bin/env python3
"""
Generic multi-stage review data models.

These models are deliberately artifact-agnostic. A review can target code,
documents, designs, proposals, specifications, or any artifact that can be
examined. Finding locations are described generically, not with code-specific
fields like line numbers or commits.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json
import uuid


class FindingSeverity(Enum):
    """Finding severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingDisposition(Enum):
    """How a finding relates to prior stage findings"""
    NEW = "new"  # Not mentioned in prior stage
    CONFIRMED = "confirmed"  # Prior finding stands
    REFUTED = "refuted"  # Prior finding is incorrect
    MODIFIED = "modified"  # Prior finding adjusted
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"  # Can't evaluate


class FindingCategory(Enum):
    """Generic finding categories (not code-specific)"""
    CORRECTNESS = "correctness"
    COMPLETENESS = "completeness"
    CLARITY = "clarity"
    PERFORMANCE = "performance"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    CONSISTENCY = "consistency"
    ASSUMPTIONS = "assumptions"
    EDGE_CASES = "edge-cases"
    REQUIREMENTS = "requirements"
    OTHER = "other"


@dataclass
class ArtifactRef:
    """Reference to artifact being reviewed"""
    location: str  # Path, URL, or identifier
    format: str  # "code", "markdown", "json", "yaml", "text", etc.
    language: Optional[str] = None  # If applicable
    size_bytes: int = 0


@dataclass
class Finding:
    """A single finding from a review"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    severity: FindingSeverity = FindingSeverity.MEDIUM
    category: FindingCategory = FindingCategory.OTHER
    subject: str = ""  # Generic location in artifact
    description: str = ""  # What was found
    evidence: str = ""  # Concrete evidence from artifact
    impact: str = ""  # Why this matters
    recommendation: str = ""  # How to address
    confidence: float = 0.8  # 0.0-1.0

    # Disposition tracking for later stages
    disposition: FindingDisposition = FindingDisposition.NEW
    prior_finding_id: Optional[str] = None  # If not NEW
    challenge_reasoning: str = ""  # Why prior finding was challenged

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        d = asdict(self)
        d['severity'] = self.severity.value
        d['category'] = self.category.value
        d['disposition'] = self.disposition.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Finding':
        """Create from dictionary"""
        d = d.copy()
        d['severity'] = FindingSeverity(d['severity'])
        d['category'] = FindingCategory(d['category'])
        d['disposition'] = FindingDisposition(d['disposition'])
        return cls(**d)


@dataclass
class WorkerOutput:
    """Output from a single worker model"""
    worker_id: str  # e.g., "sonnet-1"
    model: str  # e.g., "claude-sonnet-5"
    stage: int  # 1, 2, 3, ...
    findings: List[Finding] = field(default_factory=list)
    summary: str = ""
    confidence: float = 0.8
    duration_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    raw_response: str = ""  # Full model response


@dataclass
class ArbiterOutput:
    """Output from arbiter model for a stage"""
    arbiter_id: str
    model: str
    stage: int
    findings: List[Finding] = field(default_factory=list)
    summary: str = ""
    contradictions: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    confidence: float = 0.8
    duration_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0


@dataclass
class StageReview:
    """Results from a single review stage"""
    stage_number: int
    workers: List[WorkerOutput] = field(default_factory=list)
    arbiter: Optional[ArbiterOutput] = None
    findings: List[Finding] = field(default_factory=list)  # Deduplicated
    evidence_assessment: Dict[str, str] = field(default_factory=dict)
    overall_confidence: float = 0.8
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ReviewRequest:
    """Request to review an artifact"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    artifact_type: str = ""  # "code", "document", "design", etc.
    objective: str = ""  # What to review and why
    artifacts: List[ArtifactRef] = field(default_factory=list)
    criteria: List[str] = field(default_factory=list)  # Review criteria
    context: Dict[str, Any] = field(default_factory=dict)  # Supporting evidence
    metadata: Dict[str, Any] = field(default_factory=dict)  # Custom metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class MultiStageReviewResult:
    """Complete result from multi-stage review"""
    request: ReviewRequest
    stages: List[StageReview] = field(default_factory=list)
    final_findings: List[Finding] = field(default_factory=list)
    consensus_score: float = 0.0
    open_questions: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    completed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'request': asdict(self.request),
            'stages': [
                {
                    'stage_number': s.stage_number,
                    'findings': [f.to_dict() for f in s.findings],
                    'evidence_assessment': s.evidence_assessment,
                    'confidence': s.overall_confidence,
                    'timestamp': s.timestamp,
                }
                for s in self.stages
            ],
            'final_findings': [f.to_dict() for f in self.final_findings],
            'consensus_score': self.consensus_score,
            'open_questions': self.open_questions,
            'next_steps': self.next_steps,
            'completed_at': self.completed_at,
        }

    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(self.to_dict(), indent=2)
