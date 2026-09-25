"""
WORKER 1: Workflow Classifier
==============================

Identifies and tags workflow type for every API call.

This worker analyzes task descriptions, context size, model choice, and other
metadata to classify calls into workflow categories. Each category has different
characteristics:

- code_review: Requires semantic fidelity, security-critical
- deployment: Deterministic, repeatable, cache-friendly
- release_notes: Quality matters, can tolerate style compression
- security_review: Zero false negatives, minimize compression
- etc.

Author: Haiku 4.5
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List
from enum import Enum


class WorkflowType(Enum):
    """Enumeration of supported workflow types."""
    RELEASE_NOTES = "release_notes"
    CODE_REVIEW = "code_review"
    DEPLOYMENT = "deployment"
    ARCHITECTURE_DESIGN = "architecture_design"
    SECURITY_REVIEW = "security_review"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    DATA_ANALYSIS = "data_analysis"
    BUG_DIAGNOSIS = "bug_diagnosis"
    ALTERNATIVE_REVIEW = "alternative_review"
    UNKNOWN = "unknown"


@dataclass
class WorkflowClassification:
    """Classification result for a single API call."""
    call_id: str
    workflow_type: str
    confidence: float
    characteristics: List[str]
    recommended_compression: str  # "none", "light", "moderate", "aggressive"
    recommended_cache: str  # "none", "prefer_cache_hit", "aggressive"
    reasoning: str

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class WorkflowClassifier:
    """
    Classifies API calls into workflow types.

    Rules-based classification using task description, context size, model choice,
    and other heuristics. No ML required; simple pattern matching.
    """

    # Workflow characteristics for tuning recommendations
    WORKFLOW_PROFILES = {
        WorkflowType.RELEASE_NOTES.value: {
            "compression": "aggressive",
            "cache": "prefer_cache_hit",
            "quality_sensitive": True,
            "deterministic": True,
            "description": "Bi-weekly announcements, high documentation quality needed"
        },
        WorkflowType.CODE_REVIEW.value: {
            "compression": "light",
            "cache": "prefer_cache_hit",
            "quality_sensitive": True,
            "deterministic": False,
            "description": "Bug/feature reviews, semantic fidelity critical"
        },
        WorkflowType.DEPLOYMENT.value: {
            "compression": "moderate",
            "cache": "aggressive",
            "quality_sensitive": False,
            "deterministic": True,
            "description": "AWX/CI orchestration, repeatable, cache-friendly"
        },
        WorkflowType.ARCHITECTURE_DESIGN.value: {
            "compression": "light",
            "cache": "none",
            "quality_sensitive": True,
            "deterministic": False,
            "description": "System design, comprehensive understanding needed"
        },
        WorkflowType.SECURITY_REVIEW.value: {
            "compression": "none",
            "cache": "none",
            "quality_sensitive": True,
            "deterministic": False,
            "description": "Vulnerability analysis, zero false negatives"
        },
        WorkflowType.REFACTORING.value: {
            "compression": "light",
            "cache": "prefer_cache_hit",
            "quality_sensitive": True,
            "deterministic": False,
            "description": "Code simplification, quality of suggestions matters"
        },
        WorkflowType.DOCUMENTATION.value: {
            "compression": "aggressive",
            "cache": "prefer_cache_hit",
            "quality_sensitive": False,
            "deterministic": True,
            "description": "Writing docs, can tolerate style compression"
        },
        WorkflowType.DATA_ANALYSIS.value: {
            "compression": "moderate",
            "cache": "prefer_cache_hit",
            "quality_sensitive": True,
            "deterministic": False,
            "description": "Metrics/reporting, accuracy critical"
        },
        WorkflowType.BUG_DIAGNOSIS.value: {
            "compression": "none",
            "cache": "none",
            "quality_sensitive": True,
            "deterministic": False,
            "description": "Finding root causes, requires full context"
        },
        WorkflowType.ALTERNATIVE_REVIEW.value: {
            "compression": "light",
            "cache": "none",
            "quality_sensitive": True,
            "deterministic": False,
            "description": "External validation, quality > cost savings"
        },
    }

    # Keyword patterns for classification
    PATTERNS = {
        WorkflowType.RELEASE_NOTES.value: [
            "release note", "weekly", "bi-weekly", "announcement",
            "changelog", "update summary", "deployment summary"
        ],
        WorkflowType.CODE_REVIEW.value: [
            "code review", "pull request", "pr", "merge request", "mr",
            "bug fix", "feature", "review changes", "review code"
        ],
        WorkflowType.DEPLOYMENT.value: [
            "deploy", "deployment", "orchestrat", "awx", "ansible",
            "ci/cd", "pipeline", "release", "prod", "staging"
        ],
        WorkflowType.ARCHITECTURE_DESIGN.value: [
            "architecture", "design", "system design", "design pattern",
            "interface", "api design", "schema"
        ],
        WorkflowType.SECURITY_REVIEW.value: [
            "security", "vulnerab", "exploit", "threat", "attack",
            "cvss", "cve", "penetration", "audit", "compliance"
        ],
        WorkflowType.REFACTORING.value: [
            "refactor", "simplif", "clean up", "improve", "optimize",
            "rewrite", "consolidate"
        ],
        WorkflowType.DOCUMENTATION.value: [
            "document", "readme", "guide", "tutorial", "howto",
            "write", "explain", "clarify"
        ],
        WorkflowType.DATA_ANALYSIS.value: [
            "metric", "data", "analyz", "report", "dashboard",
            "statistics", "aggregate", "trend"
        ],
        WorkflowType.BUG_DIAGNOSIS.value: [
            "debug", "diagnose", "root cause", "error", "bug",
            "trace", "investigate", "troubleshoot"
        ],
        WorkflowType.ALTERNATIVE_REVIEW.value: [
            "second opinion", "alternative", "external review",
            "verify", "validate", "consensus"
        ],
    }

    def __init__(self):
        """Initialize the classifier."""
        self.call_counter = 0

    def classify(
        self,
        task_description: str,
        context_size: Optional[int] = None,
        model: Optional[str] = None,
        call_id: Optional[str] = None
    ) -> WorkflowClassification:
        """
        Classify an API call into a workflow type.

        Args:
            task_description: Description of the task
            context_size: Size of context in tokens (optional)
            model: Model being used (haiku, sonnet, opus, gemini)
            call_id: Unique call ID (auto-generated if not provided)

        Returns:
            WorkflowClassification with type, confidence, characteristics,
            and recommendations for compression/caching
        """
        self.call_counter += 1
        if call_id is None:
            call_id = f"call_{self.call_counter:06d}"

        # Normalize input
        task_lower = task_description.lower()

        # Score each workflow type
        scores = self._score_workflows(task_lower, context_size, model)

        # Find best match
        best_type = max(scores.keys(), key=lambda k: scores[k])
        confidence = scores[best_type]

        # Get characteristics and recommendations
        profile = self.WORKFLOW_PROFILES.get(best_type, {})
        characteristics = self._extract_characteristics(best_type, task_lower)

        # Create classification result
        return WorkflowClassification(
            call_id=call_id,
            workflow_type=best_type,
            confidence=confidence,
            characteristics=characteristics,
            recommended_compression=profile.get("compression", "moderate"),
            recommended_cache=profile.get("cache", "prefer_cache_hit"),
            reasoning=self._generate_reasoning(best_type, confidence, characteristics)
        )

    def _score_workflows(
        self,
        task_lower: str,
        context_size: Optional[int] = None,
        model: Optional[str] = None
    ) -> dict:
        """Score each workflow type based on keyword matches."""
        scores = {}

        for workflow_type in WorkflowType:
            if workflow_type == WorkflowType.UNKNOWN:
                continue

            type_str = workflow_type.value
            patterns = self.PATTERNS.get(type_str, [])

            # Count keyword matches
            match_count = sum(1 for pattern in patterns if pattern in task_lower)
            base_score = match_count / max(len(patterns), 1)

            # Apply modifiers based on context size
            if context_size is not None:
                if context_size > 100000 and type_str == WorkflowType.BUG_DIAGNOSIS.value:
                    base_score *= 1.2  # Big context favors bug diagnosis
                elif context_size < 5000 and type_str == WorkflowType.DEPLOYMENT.value:
                    base_score *= 1.1  # Small context favors deployment

            # Apply modifiers based on model
            if model:
                if model.lower() == "opus" and type_str == WorkflowType.SECURITY_REVIEW.value:
                    base_score *= 1.15  # Opus often used for security
                elif model.lower() == "haiku" and type_str == WorkflowType.DOCUMENTATION.value:
                    base_score *= 1.1   # Haiku good for documentation

            scores[type_str] = base_score

        # If no matches, default to unknown with lowest confidence
        if max(scores.values()) == 0:
            scores = {wf.value: 0.0 for wf in WorkflowType if wf != WorkflowType.UNKNOWN}
            scores[WorkflowType.UNKNOWN.value] = 0.1

        # Normalize scores to confidence [0, 1]
        max_score = max(scores.values()) if scores.values() else 1.0
        if max_score > 0:
            scores = {k: v / max_score for k, v in scores.items()}

        return scores

    def _extract_characteristics(self, workflow_type: str, task_lower: str) -> List[str]:
        """Extract characteristic tags for a workflow."""
        characteristics = []

        profile = self.WORKFLOW_PROFILES.get(workflow_type, {})

        if profile.get("quality_sensitive"):
            characteristics.append("quality_sensitive")
        if profile.get("deterministic"):
            characteristics.append("deterministic")

        # Add custom characteristics based on keywords
        if "security" in task_lower or "vulnerab" in task_lower:
            characteristics.append("security_critical")
        if "consensus" in task_lower:
            characteristics.append("consensus_required")
        if "code" in task_lower:
            characteristics.append("code_analysis")

        return characteristics

    def _generate_reasoning(
        self,
        workflow_type: str,
        confidence: float,
        characteristics: List[str]
    ) -> str:
        """Generate human-readable reasoning for classification."""
        profile = self.WORKFLOW_PROFILES.get(workflow_type, {})
        return (
            f"Classified as {workflow_type} (confidence: {confidence:.0%}). "
            f"{profile.get('description', '')} "
            f"Characteristics: {', '.join(characteristics) if characteristics else 'none'}."
        )

    def save_classification(
        self,
        classification: WorkflowClassification,
        output_file: Optional[Path] = None
    ) -> None:
        """Save classification result to file."""
        if output_file is None:
            output_file = Path.home() / ".claude" / "metrics" / "classifications.jsonl"

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "a") as f:
            f.write(json.dumps(classification.to_dict()) + "\n")

    def get_profile(self, workflow_type: str) -> dict:
        """Get the full profile for a workflow type."""
        return self.WORKFLOW_PROFILES.get(workflow_type, {})


def main():
    """Demo the classifier."""
    classifier = WorkflowClassifier()

    test_cases = [
        ("Code review for PR #123", "code_review"),
        ("Deploy to production", "deployment"),
        ("Security vulnerability analysis", "security_review"),
        ("Bi-weekly release notes", "release_notes"),
        ("Debug database connection issue", "bug_diagnosis"),
    ]

    print("Workflow Classification Demo")
    print("=" * 60)

    for task, expected_type in test_cases:
        classification = classifier.classify(task)
        match = "✓" if classification.workflow_type == expected_type else "✗"
        print(f"\n{match} Task: {task}")
        print(f"  Type: {classification.workflow_type} (confidence: {classification.confidence:.0%})")
        print(f"  Compression: {classification.recommended_compression}")
        print(f"  Cache: {classification.recommended_cache}")
        if classification.characteristics:
            print(f"  Characteristics: {', '.join(classification.characteristics)}")


if __name__ == "__main__":
    main()
