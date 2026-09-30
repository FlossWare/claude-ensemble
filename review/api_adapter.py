#!/usr/bin/env python3
"""
API adapter to connect to real Claude models via Anthropic SDK.

Supports both real API calls and mock responses for testing.
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RealAPIClient:
    """Real Anthropic API client"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package required: pip install anthropic")

    def call_model(self, model: str, prompt: str) -> str:
        """Call real Claude model"""
        logger.info(f"Calling {model}...")

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise


class MockAPIClient:
    """Mock API client with realistic responses"""

    def __init__(self):
        self.call_count = 0

    def call_model(self, model: str, prompt: str) -> str:
        """Return mock response that looks realistic"""
        self.call_count += 1

        # Detect if this is Stage 1 or Stage 2 based on prompt content
        is_stage2 = "challenge" in prompt.lower() or "prior" in prompt.lower()
        is_arbiter = "synthesis" in prompt.lower() or "synthesize" in prompt.lower()

        if is_stage2 and not is_arbiter:
            # Stage 2 worker - finds issues
            return json.dumps({
                "findings": [
                    {
                        "id": "finding-s2-001",
                        "subject": "Missing type hints in WorkerOutput",
                        "description": "WorkerOutput.raw_response field lacks type annotation",
                        "evidence": "raw_response: str  # Should be Optional[str]",
                        "severity": "medium",
                        "category": "correctness",
                        "confidence": 0.85,
                        "disposition": "new",
                    },
                    {
                        "id": "finding-s2-002",
                        "subject": "Incomplete error handling in pipeline",
                        "description": "Worker failures don't preserve artifact state",
                        "evidence": "Exception in _run_workers silently continues without logging worker name",
                        "severity": "high",
                        "category": "correctness",
                        "confidence": 0.9,
                        "disposition": "new",
                    },
                    {
                        "id": "finding-s2-003",
                        "subject": "Cost tracking not integrated with workers",
                        "description": "StageCost tracks tokens but workers don't report them",
                        "evidence": "WorkerOutput has tokens_used=0, never populated from API",
                        "severity": "high",
                        "category": "completeness",
                        "confidence": 0.95,
                        "disposition": "new",
                    },
                ],
                "summary": "Stage 2 analysis: Found 3 issues in implementation, especially cost tracking gaps",
                "confidence": 0.90,
            })

        elif is_stage2 and is_arbiter:
            # Stage 2 arbiter - synthesizes with dispositions
            return json.dumps({
                "findings": [
                    {
                        "id": "finding-arb2-001",
                        "subject": "Missing type hints in WorkerOutput",
                        "description": "raw_response field should be Optional[str]",
                        "evidence": "raw_response: str  # Could be None on API failure",
                        "severity": "medium",
                        "category": "correctness",
                        "confidence": 0.85,
                        "disposition": "confirmed",
                        "prior_finding_id": "finding-s2-001",
                    },
                    {
                        "id": "finding-arb2-002",
                        "subject": "Worker exception handling insufficient",
                        "description": "Silent failures in _run_workers don't preserve state properly",
                        "evidence": "Exception caught but worker_id not logged, makes debugging hard",
                        "severity": "high",
                        "category": "correctness",
                        "confidence": 0.92,
                        "disposition": "confirmed",
                        "prior_finding_id": "finding-s2-002",
                    },
                    {
                        "id": "finding-arb2-003",
                        "subject": "Token usage not tracked from API",
                        "description": "Cost tracking infrastructure in place but not connected to actual API calls",
                        "evidence": "StageCost.worker_tokens always 0 because API client mock doesn't return usage",
                        "severity": "high",
                        "category": "completeness",
                        "confidence": 0.96,
                        "disposition": "confirmed",
                        "prior_finding_id": "finding-s2-003",
                    },
                ],
                "summary": "All 3 Stage 2 findings confirmed. Token tracking is critical blocker for cost reporting.",
                "contradictions": [],
                "unresolved": ["How to get token usage from mock API client"],
                "confidence": 0.93,
            })

        else:
            # Stage 1 worker/arbiter - basic analysis
            return json.dumps({
                "findings": [
                    {
                        "id": "finding-s1-001",
                        "subject": "Generic review system architecture",
                        "description": "Architecture correctly separates concerns (models, config, storage, pipeline)",
                        "evidence": "Each module has single responsibility: models.py defines schema, pipeline.py orchestrates",
                        "severity": "info",
                        "category": "correctness",
                        "confidence": 0.95,
                        "disposition": "new",
                    },
                    {
                        "id": "finding-s1-002",
                        "subject": "Finding disposition tracking",
                        "description": "Disposition enum correctly captures finding evolution (NEW/CONFIRMED/REFUTED/MODIFIED)",
                        "evidence": "FindingDisposition enum in models.py supports all required states",
                        "severity": "info",
                        "category": "correctness",
                        "confidence": 0.98,
                        "disposition": "new",
                    },
                ],
                "summary": "Stage 1: Architecture is sound, core abstractions are correct. Some integration gaps remain.",
                "confidence": 0.88,
            })

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens in text"""
        # Rough: 1 token per 4 chars
        return len(text) // 4

    def estimate_cost(self, tokens: int, model: str) -> float:
        """Estimate cost for tokens"""
        # Pricing as of 2026-09
        pricing = {
            "claude-haiku-4-5": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
            "claude-sonnet-5": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
            "claude-opus-5-5": {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
        }
        rate = pricing.get(model, {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000})
        # Assume 30% input, 70% output
        return tokens * (rate["input"] * 0.3 + rate["output"] * 0.7)


def get_api_client(use_real: bool = False) -> object:
    """Get API client (real or mock)"""
    if use_real and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return RealAPIClient()
        except Exception as e:
            logger.warning(f"Real API unavailable: {e}, falling back to mock")
            return MockAPIClient()
    else:
        return MockAPIClient()
