#!/usr/bin/env python3
"""
Execute review workers for a given stage.

Workers independently examine the original artifact and produce findings.
Later-stage workers receive prior findings as context to challenge.
"""

import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

from .models import ReviewRequest, WorkerOutput, Finding, StageReview
from .config import StageConfig
from .prompts import build_worker_prompt

logger = logging.getLogger(__name__)


class WorkerRunner:
    """Execute workers for a review stage"""

    def __init__(self, api_client, request: ReviewRequest, stage_config: StageConfig):
        self.api_client = api_client
        self.request = request
        self.stage_config = stage_config

    def run_workers(
        self,
        artifacts: Dict[str, str],
        prior_stages: Optional[List[StageReview]] = None,
    ) -> List[WorkerOutput]:
        """Execute all workers for this stage"""
        worker_outputs = []

        # Build worker models list
        if self.stage_config.worker_models:
            models = self.stage_config.worker_models
        else:
            # Auto-select from tier
            models = self._select_worker_models(self.stage_config.num_workers)

        logger.info(f"Running {len(models)} workers for stage {self.stage_config.stage_number}")

        for i, model in enumerate(models, 1):
            worker_id = f"{model.split('/')[-1][:10]}-{i}"

            try:
                output = self._run_single_worker(
                    worker_id=worker_id,
                    model=model,
                    artifacts=artifacts,
                    prior_stages=prior_stages,
                )
                worker_outputs.append(output)
                logger.info(f"  ✓ {worker_id}: {len(output.findings)} findings")
            except Exception as e:
                logger.error(f"  ✗ {worker_id} failed: {e}")
                # Continue with other workers

        return worker_outputs

    def _select_worker_models(self, count: int) -> List[str]:
        """Select N diverse worker models for this stage"""
        # TODO: Integrate with existing ModelPool from orchestrator
        # For now, return placeholder models
        tier = self.stage_config.worker_tier
        tier_models = {
            'cheap': ['claude-haiku-4-5-20251001'],
            'balanced': ['claude-sonnet-5', 'claude-sonnet-5', 'claude-sonnet-5'],  # Can repeat in pool
            'expensive': ['claude-opus-5-5', 'claude-opus-5-5', 'claude-opus-5-5'],
        }
        models = tier_models.get(tier, ['claude-sonnet-5'])
        return models[:count]

    def _run_single_worker(
        self,
        worker_id: str,
        model: str,
        artifacts: Dict[str, str],
        prior_stages: Optional[List[StageReview]] = None,
    ) -> WorkerOutput:
        """Run a single worker model"""
        # Merge artifacts into single context
        artifact_content = "\n\n---\n\n".join(artifacts.values())

        # Build prompt
        prompt = build_worker_prompt(
            request=self.request,
            stage_config=self.stage_config,
            worker_id=worker_id,
            artifact_content=artifact_content,
            prior_stages=prior_stages,
        )

        # Call API
        logger.debug(f"Calling {model} with {len(prompt)} char prompt")

        # In production, call real API
        response_text, tokens_used, cost = self._call_model(model, prompt)

        # Parse response
        findings = self._parse_findings(response_text)

        # Build output
        output = WorkerOutput(
            worker_id=worker_id,
            model=model,
            stage=self.stage_config.stage_number,
            findings=findings,
            summary=self._extract_summary(response_text),
            confidence=self._estimate_confidence(findings),
            tokens_used=tokens_used,
            cost_usd=cost,
            raw_response=response_text,
        )

        return output

    def _call_model(self, model: str, prompt: str) -> tuple:
        """Call model API. Returns (response_text, tokens_used, cost)"""
        if not self.api_client:
            raise RuntimeError("API client required for worker execution. Cannot use mock fallbacks.")
        return self.api_client.call_model(model, prompt)

    def _parse_findings(self, response_text: str) -> List[Finding]:
        """Parse findings from model response"""
        try:
            data = json.loads(response_text)
            findings = []

            for finding_data in data.get("findings", []):
                finding = Finding.from_dict(finding_data)
                findings.append(finding)

            return findings
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse findings from response: {e}")
            return []

    def _extract_summary(self, response_text: str) -> str:
        """Extract summary from response"""
        try:
            data = json.loads(response_text)
            return data.get("summary", "")
        except json.JSONDecodeError:
            return ""

    def _estimate_confidence(self, findings: List[Finding]) -> float:
        """Estimate worker confidence based on findings"""
        if not findings:
            return 0.5

        avg_confidence = sum(f.confidence for f in findings) / len(findings)
        return min(0.95, avg_confidence + 0.05)  # Slight boost for having findings
