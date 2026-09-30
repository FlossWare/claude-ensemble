#!/usr/bin/env python3
"""
Execute review arbiter for a given stage.

Arbiter synthesizes worker findings, challenges prior conclusions,
and produces a stage review with explicit dispositions.
"""

import json
import logging
from typing import List, Dict, Optional

from .models import (
    ReviewRequest, WorkerOutput, ArbiterOutput, Finding, FindingDisposition,
    StageReview
)
from .config import StageConfig
from .prompts import build_arbiter_prompt

logger = logging.getLogger(__name__)


class ArbiterRunner:
    """Execute arbiter for a review stage"""

    def __init__(self, api_client, request: ReviewRequest, stage_config: StageConfig):
        self.api_client = api_client
        self.request = request
        self.stage_config = stage_config

    def run_arbiter(
        self,
        artifacts: Dict[str, str],
        worker_outputs: List[WorkerOutput],
        prior_findings: Optional[List[Finding]] = None,
    ) -> ArbiterOutput:
        """Execute arbiter synthesis"""
        # Merge artifacts
        artifact_content = "\n\n---\n\n".join(artifacts.values())

        # Build worker findings dict for prompting
        worker_findings_dict = {}
        for worker in worker_outputs:
            worker_findings_dict[worker.worker_id] = worker.findings

        # Build prompt
        prompt = build_arbiter_prompt(
            request=self.request,
            stage_config=self.stage_config,
            artifact_content=artifact_content,
            worker_findings=worker_findings_dict,
            prior_findings=prior_findings,
        )

        logger.debug(f"Calling arbiter {self.stage_config.arbiter_model} with {len(prompt)} char prompt")

        # Call API
        response_text = self._call_arbiter_model(
            self.stage_config.arbiter_model or "claude-opus-5-5",
            prompt
        )

        # Parse response
        findings = self._parse_findings(response_text)

        # Consolidate and track dispositions
        final_findings, dispositions = self._consolidate_findings(
            worker_findings=worker_outputs,
            arbiter_findings=findings,
            prior_findings=prior_findings,
        )

        # Build arbiter output
        output = ArbiterOutput(
            arbiter_id=self.stage_config.arbiter_model or "arbiter-auto",
            model=self.stage_config.arbiter_model or "claude-opus-5-5",
            stage=self.stage_config.stage_number,
            findings=final_findings,
            summary=self._extract_summary(response_text),
            confidence=self._estimate_confidence(final_findings),
        )

        return output

    def _call_arbiter_model(self, model: str, prompt: str) -> str:
        """Call arbiter model API"""
        if self.api_client:
            return self.api_client.call_model(model, prompt)
        else:
            # Fallback mock response
            logger.debug(f"No API client, returning mock response")
            return json.dumps({
                "findings": [],
                "summary": "Mock arbiter synthesis",
                "contradictions": [],
                "unresolved": [],
                "confidence": 0.8,
            })

    def _parse_findings(self, response_text: str) -> List[Finding]:
        """Parse findings from arbiter response"""
        try:
            data = json.loads(response_text)
            findings = []

            for finding_data in data.get("findings", []):
                finding = Finding.from_dict(finding_data)
                findings.append(finding)

            return findings
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse arbiter findings: {e}")
            return []

    def _consolidate_findings(
        self,
        worker_findings: List[WorkerOutput],
        arbiter_findings: List[Finding],
        prior_findings: Optional[List[Finding]] = None,
    ) -> tuple:
        """
        Consolidate findings from workers and arbiter.

        Merges duplicates, tracks dispositions, preserves evidence.

        Returns: (final_findings, dispositions_dict)
        """
        # Collect all worker findings
        all_worker_findings = []
        for worker in worker_findings:
            all_worker_findings.extend(worker.findings)

        # Map prior findings by subject for comparison
        prior_by_subject = {}
        if prior_findings:
            for finding in prior_findings:
                prior_by_subject[finding.subject] = finding

        # Process arbiter findings
        final_findings = []
        dispositions = {}

        for arbiter_finding in arbiter_findings:
            # Check if this matches a prior finding
            prior = prior_by_subject.get(arbiter_finding.subject)

            if prior:
                # Mark disposition based on arbiter assessment
                if arbiter_finding.disposition == FindingDisposition.CONFIRMED:
                    arbiter_finding.prior_finding_id = prior.id
                    dispositions[prior.id] = "confirmed"
                elif arbiter_finding.disposition == FindingDisposition.REFUTED:
                    arbiter_finding.prior_finding_id = prior.id
                    dispositions[prior.id] = "refuted"
                elif arbiter_finding.disposition == FindingDisposition.MODIFIED:
                    arbiter_finding.prior_finding_id = prior.id
                    dispositions[prior.id] = "modified"

            final_findings.append(arbiter_finding)

        # Preserve evidence from worker findings that arbiter confirmed
        final_findings = self._enrich_findings_with_evidence(
            final_findings,
            all_worker_findings,
        )

        return final_findings, dispositions

    def _enrich_findings_with_evidence(
        self,
        arbiter_findings: List[Finding],
        worker_findings: List[Finding],
    ) -> List[Finding]:
        """
        Enrich arbiter findings with evidence from worker findings.

        Ensures evidence is preserved for independent verification.
        """
        worker_by_subject = {}
        for finding in worker_findings:
            if finding.subject not in worker_by_subject:
                worker_by_subject[finding.subject] = finding

        for arbiter_finding in arbiter_findings:
            if not arbiter_finding.evidence:
                # Try to get evidence from worker findings
                worker_finding = worker_by_subject.get(arbiter_finding.subject)
                if worker_finding and worker_finding.evidence:
                    arbiter_finding.evidence = worker_finding.evidence

        return arbiter_findings

    def _extract_summary(self, response_text: str) -> str:
        """Extract summary from response"""
        try:
            data = json.loads(response_text)
            return data.get("summary", "")
        except json.JSONDecodeError:
            return ""

    def _estimate_confidence(self, findings: List[Finding]) -> float:
        """Estimate arbiter confidence based on findings"""
        if not findings:
            return 0.5

        avg_confidence = sum(f.confidence for f in findings) / len(findings)
        return min(0.95, avg_confidence)
