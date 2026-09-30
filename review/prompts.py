#!/usr/bin/env python3
"""
Prompt generation for multi-stage reviews.

Builds worker and arbiter prompts that maintain the core principle:
every stage independently reviews the ORIGINAL artifact, with prior reviews
treated as untrusted evidence to challenge, not conclusions to inherit.
"""

import json
import logging
from typing import List, Optional, Dict, Any

from .models import ReviewRequest, ArtifactRef, StageReview, Finding
from .config import StageConfig, StageRole

logger = logging.getLogger(__name__)


class WorkerPromptBuilder:
    """Build prompts for review workers"""

    def __init__(self, request: ReviewRequest, stage_config: StageConfig, worker_id: str):
        self.request = request
        self.stage_config = stage_config
        self.worker_id = worker_id

    def build_artifact_context(self) -> str:
        """Build context showing the artifact being reviewed"""
        parts = []

        for artifact in self.request.artifacts:
            parts.append(f"## Artifact: {artifact.location}")
            parts.append(f"Format: {artifact.format}")
            if artifact.language:
                parts.append(f"Language: {artifact.language}")
            parts.append("")

        return "\n".join(parts)

    def build_objective_context(self) -> str:
        """Build context showing the review objective"""
        return f"""## Review Objective

User's Request:
{self.request.objective}

Criteria to Consider:
{chr(10).join(f"- {c}" for c in self.request.criteria) if self.request.criteria else "- General correctness and completeness"}
"""

    def build_prior_findings_context(self, prior_stages: List[StageReview]) -> str:
        """Build context showing findings from prior stages (if any)"""
        if not prior_stages:
            return ""

        parts = ["## Prior Stage Findings (for reference)"]

        for stage in prior_stages:
            parts.append(f"\n### Stage {stage.stage_number} Findings ({len(stage.findings)} total)")
            for finding in stage.findings:
                parts.append(f"- [{finding.severity.value.upper()}] {finding.description}")
                parts.append(f"  Confidence: {finding.confidence:.1%}")

        return "\n".join(parts)

    def build_anti_anchoring_instructions(self) -> str:
        """Build instructions to prevent anchoring bias in later stages"""
        if self.stage_config.stage_number == 1:
            return """## Instructions

Conduct an independent, thorough analysis of this artifact.

Focus on:
- Correctness and logical soundness
- Completeness against stated criteria
- Potential issues or concerns
- Areas that could be improved
- Any assumptions that may be incorrect

Assume no prior review has been conducted. Analyze from first principles.
"""

        else:
            return f"""## Instructions

You are reviewing the ORIGINAL artifact for the second+ time.

The findings shown above are from Stage {self.stage_config.stage_number - 1}.
These are NOT ground truth—treat them as preliminary hypotheses to validate or refute.

**Your task:**

1. Review the original artifact independently
2. Look for things prior reviewers might have missed
3. Challenge the prior findings:
   - Which are well-supported by evidence?
   - Which lack sufficient evidence?
   - Which might be false positives?
4. Identify assumptions prior reviewers made without justification
5. Look for edge cases or interactions they missed
6. Identify any areas where prior analysis stopped too early

**Do not simply confirm prior findings. Actively look for problems with them.**

Specifically look for:
- Findings contradicted by the artifact
- Requirements prior reviewers overlooked
- Alternative interpretations of ambiguous sections
- Interactions between findings (one assumes another, creating circular logic)
- Missing context that changes the assessment
"""

    def build_output_format_instructions(self) -> str:
        """Build instructions for structured output"""
        return """## Output Format

Respond with a JSON object containing:

{
  "findings": [
    {
      "subject": "Where in the artifact (e.g., section name, function name, concept)",
      "description": "What you found",
      "evidence": "Exact quote or reference from the artifact",
      "severity": "critical|high|medium|low|info",
      "category": "correctness|completeness|clarity|performance|security|etc",
      "impact": "Why this matters",
      "recommendation": "How to address",
      "confidence": 0.85
    }
  ],
  "summary": "Overall assessment (2-3 sentences)",
  "confidence": 0.8
}

Guidelines:
- Be specific. "subject" and "evidence" must reference the actual artifact
- Only include findings with confidence >= 0.5
- Keep evidence quotes brief but complete
- Categories: correctness, completeness, clarity, performance, security, maintainability, consistency, assumptions, edge-cases, requirements, other
"""

    def build_full_prompt(self, artifact_content: str, prior_stages: Optional[List[StageReview]] = None) -> str:
        """Build complete worker prompt"""
        parts = [
            "# Code/Document Review",
            "",
            self.build_artifact_context(),
            "",
            self.build_objective_context(),
            "",
            "## Artifact Content",
            "",
            "```",
            artifact_content,
            "```",
            "",
        ]

        if prior_stages:
            parts.append(self.build_prior_findings_context(prior_stages))
            parts.append("")

        parts.append(self.build_anti_anchoring_instructions())
        parts.append("")
        parts.append(self.build_output_format_instructions())

        return "\n".join(parts)


class ArbiterPromptBuilder:
    """Build prompts for review arbiters"""

    def __init__(self, request: ReviewRequest, stage_config: StageConfig):
        self.request = request
        self.stage_config = stage_config

    def build_worker_summary(self, worker_findings: Dict[str, List[Finding]]) -> str:
        """Build summary of worker findings"""
        parts = ["## Worker Findings Summary"]

        for worker_id, findings in worker_findings.items():
            parts.append(f"\n### {worker_id}")
            if not findings:
                parts.append("(No findings)")
            else:
                for f in findings:
                    parts.append(
                        f"- [{f.severity.value.upper()}] {f.description} "
                        f"(confidence: {f.confidence:.1%})"
                    )

        return "\n".join(parts)

    def build_synthesis_instructions(self, stage_number: int, prior_findings: Optional[List[Finding]] = None) -> str:
        """Build instructions for arbiter synthesis"""
        base = """## Arbiter Task

Synthesize the worker findings above. Your goal is to:

1. Identify duplicate or overlapping findings
2. Assess evidence quality for each finding
3. Identify contradictions
4. Determine overall confidence in key findings
5. Flag findings that lack sufficient evidence
6. Identify areas needing additional investigation
"""

        if stage_number > 1 and prior_findings:
            base += f"""
## Prior Stage ({stage_number - 1}) Findings

Previous arbiter identified {len(prior_findings)} findings.
Your task now includes:
- Do you confirm these?
- Do you refute any?
- Did they miss something important?
- Are any claims contradicted by the artifact?
"""

        base += """
**Important:** Majority vote is not enough. A single well-evidenced finding
outweighs consensus without evidence. Report your honest assessment of what
the artifact actually shows.
"""

        return base

    def build_output_format_instructions(self) -> str:
        """Build instructions for arbiter output"""
        return """## Output Format

Respond with a JSON object:

{
  "findings": [
    {
      "subject": "Key issue or finding",
      "description": "Assessment",
      "evidence": "Supporting evidence from artifact",
      "severity": "critical|high|medium|low|info",
      "category": "correctness|completeness|clarity|etc",
      "confidence": 0.85,
      "disposition": "new|confirmed|refuted|modified",
      "prior_finding_id": "id_if_modifying_prior_finding"
    }
  ],
  "summary": "Executive summary (3-4 sentences)",
  "contradictions": ["List of conflicting findings within or between stages"],
  "unresolved": ["Issues needing further investigation"],
  "confidence": 0.85
}

Disposition values:
- "new": Finding not mentioned in prior stages
- "confirmed": Prior finding is well-supported
- "refuted": Prior finding is incorrect
- "modified": Prior finding is partially correct, but needs adjustment
"""

    def build_full_prompt(
        self,
        artifact_content: str,
        worker_findings: Dict[str, List[Finding]],
        prior_findings: Optional[List[Finding]] = None,
    ) -> str:
        """Build complete arbiter prompt"""
        parts = [
            "# Review Synthesis",
            "",
            "## Objective",
            f"{self.request.objective}",
            "",
            "## Artifact Content",
            "",
            "```",
            artifact_content,
            "```",
            "",
            self.build_worker_summary(worker_findings),
            "",
            self.build_synthesis_instructions(self.stage_config.stage_number, prior_findings),
            "",
            self.build_output_format_instructions(),
        ]

        return "\n".join(parts)


def build_worker_prompt(
    request: ReviewRequest,
    stage_config: StageConfig,
    worker_id: str,
    artifact_content: str,
    prior_stages: Optional[List[StageReview]] = None,
) -> str:
    """Build complete prompt for a worker"""
    builder = WorkerPromptBuilder(request, stage_config, worker_id)
    return builder.build_full_prompt(artifact_content, prior_stages)


def build_arbiter_prompt(
    request: ReviewRequest,
    stage_config: StageConfig,
    artifact_content: str,
    worker_findings: Dict[str, List[Finding]],
    prior_findings: Optional[List[Finding]] = None,
) -> str:
    """Build complete prompt for an arbiter"""
    builder = ArbiterPromptBuilder(request, stage_config)
    return builder.build_full_prompt(artifact_content, worker_findings, prior_findings)
