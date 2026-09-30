#!/usr/bin/env python3
"""
Multi-stage solution solving data models.

Solutions are proposed by workers, consolidated by arbiters, and challenged/refined
through multiple stages (solve, meta-solve, meta-meta-solve, etc.).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json
import uuid


class SolutionStatus(Enum):
    """Solution viability status"""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    HYBRID = "hybrid"  # Combines multiple solutions
    NEEDS_REVIEW = "needs-review"
    IMPLEMENTED = "implemented"


class SolutionDisposition(Enum):
    """How a solution relates to prior stage solutions"""
    NEW = "new"  # First time proposed
    ACCEPTED_FORWARD = "accepted-forward"  # Prior solution retained
    REFINED = "refined"  # Prior solution improved
    REJECTED = "rejected"  # Prior solution dismissed
    SUPERSEDED = "superseded"  # Replaced by better solution
    HYBRID = "hybrid"  # Combined with other solutions


class SolutionRiskLevel(Enum):
    """Risk assessment for a solution"""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SolutionCategory(Enum):
    """Types of solutions"""
    ARCHITECTURAL = "architectural"
    ALGORITHMIC = "algorithmic"
    IMPLEMENTATION = "implementation"
    CONFIGURATION = "configuration"
    OPERATIONAL = "operational"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    MIGRATION = "migration"
    OTHER = "other"


@dataclass
class SolutionProposal:
    """A proposed solution to a problem"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    problem_statement: str = ""  # What are we solving?
    solution_description: str = ""  # How does it work?
    category: SolutionCategory = SolutionCategory.IMPLEMENTATION
    status: SolutionStatus = SolutionStatus.PROPOSED

    # Evaluation metrics
    confidence: float = 0.8  # 0.0-1.0
    risk_level: SolutionRiskLevel = SolutionRiskLevel.MEDIUM

    # Impact assessment
    effort_estimate: str = ""  # "2 days", "1 week", etc.
    cost_estimate: float = 0.0  # $ or API cost
    benefits: str = ""  # Positive outcomes
    drawbacks: str = ""  # Negative impacts
    dependencies: List[str] = field(default_factory=list)  # What's needed first

    # Justification
    evidence: str = ""  # Why this works
    tradeoffs: str = ""  # Pros/cons vs alternatives

    # Disposition tracking for later stages
    disposition: SolutionDisposition = SolutionDisposition.NEW
    prior_solution_id: Optional[str] = None  # If not NEW
    refinement_reasoning: str = ""  # How/why was it refined

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        d = asdict(self)
        d['category'] = self.category.value
        d['status'] = self.status.value
        d['risk_level'] = self.risk_level.value
        d['disposition'] = self.disposition.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'SolutionProposal':
        """Create from dictionary"""
        d = d.copy()
        d['category'] = SolutionCategory(d['category'])
        d['status'] = SolutionStatus(d['status'])
        d['risk_level'] = SolutionRiskLevel(d['risk_level'])
        d['disposition'] = SolutionDisposition(d['disposition'])
        return cls(**d)


@dataclass
class SolveWorkerOutput:
    """Output from a worker proposing solutions"""
    worker_id: str
    model: str = ""
    solutions: List[SolutionProposal] = field(default_factory=list)
    reasoning: str = ""  # How/why these solutions were chosen
    confidence_score: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    raw_response: str = ""  # Full API response


@dataclass
class SolveArbiterOutput:
    """Arbiter consolidation of worker solutions"""
    model: str = ""
    solutions: List[SolutionProposal] = field(default_factory=list)  # Final synthesized
    selected_solution: Optional[SolutionProposal] = None  # Best overall
    alternative_solutions: List[SolutionProposal] = field(default_factory=list)  # Also viable
    hybrid_solution: Optional[SolutionProposal] = None  # If combining multiple
    reasoning: str = ""  # Why this choice
    consensus_score: float = 0.0  # Agreement across workers
    tokens_used: int = 0
    cost_usd: float = 0.0
    raw_response: str = ""  # Full API response


@dataclass
class SolveRequest:
    """Request to solve one or more problems"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    problems: List[str] = field(default_factory=list)  # Problem statements
    context: str = ""  # Background/constraints
    objective: str = ""  # What success looks like
    constraints: List[str] = field(default_factory=list)  # What we can't do
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SolveResult:
    """Result of multi-stage solving"""
    request_id: str
    num_stages: int
    solutions_by_stage: Dict[int, List[SolutionProposal]] = field(default_factory=dict)
    final_solution: Optional[SolutionProposal] = None
    total_cost: float = 0.0
    total_tokens: int = 0
    consensus_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
