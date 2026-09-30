#!/usr/bin/env python3
"""
Solve stage workers - generate solution proposals via Claude API
"""

import json
import logging
from typing import List, Optional
from .models import SolutionProposal, SolveWorkerOutput

logger = logging.getLogger(__name__)


class SolveWorkerRunner:
    """Execute solve workers for generating solution proposals"""

    def __init__(self, api_client, request, stage_config):
        self.api_client = api_client
        self.request = request
        self.stage_config = stage_config

    def run_workers(
        self,
        problems: List[str],
        prior_solutions: Optional[List[SolutionProposal]] = None,
    ) -> List[SolveWorkerOutput]:
        """Execute all workers for this solve stage"""
        if not self.api_client:
            raise RuntimeError("API client required for solve workers")

        worker_outputs = []

        # Determine worker models
        if self.stage_config.worker_models:
            models = self.stage_config.worker_models
        else:
            models = self._select_worker_models()

        logger.info(f"Running {len(models)} workers for stage {self.stage_config.stage_number}")

        for i, model in enumerate(models, 1):
            worker_id = f"worker-{self.stage_config.stage_number}-{i}"

            try:
                output = self._run_single_worker(
                    worker_id, model, problems, prior_solutions
                )
                worker_outputs.append(output)
            except Exception as e:
                logger.error(f"Worker {worker_id} failed: {e}")
                raise

        return worker_outputs

    def _run_single_worker(
        self, worker_id: str, model: str, problems: List[str], prior_solutions
    ) -> SolveWorkerOutput:
        """Run a single worker to propose solutions"""
        prompt = self._build_worker_prompt(problems, prior_solutions)

        response_text, tokens_used, cost_usd = self.api_client.call_model(
            model, prompt
        )

        # Parse solutions from response
        solutions = self._parse_solutions(response_text)

        output = SolveWorkerOutput(
            worker_id=worker_id,
            model=model,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            solutions=solutions,
            raw_response=response_text,
        )

        logger.info(
            f"Worker {worker_id} generated {len(solutions)} solutions ({tokens_used} tokens)"
        )
        return output

    def _build_worker_prompt(self, problems: List[str], prior_solutions) -> str:
        """Build prompt for worker"""
        prompt = f"""You are a solution architect. Generate creative, feasible solutions to these problems:

{chr(10).join(f'{i+1}. {p}' for i, p in enumerate(problems))}

Context: {self.request.context}
Objective: {self.request.objective}

"""

        if prior_solutions:
            prompt += f"""Prior solutions from previous stage (challenge and refine these):
{chr(10).join(f"- {s.solution_description[:100]}" for s in prior_solutions)}

"""

        prompt += """Return JSON array of solutions with this structure:
[
  {
    "problem_statement": "the problem",
    "solution_description": "detailed solution",
    "category": "ARCHITECTURAL|ALGORITHMIC|IMPLEMENTATION|...",
    "confidence": 0.85,
    "effort_estimate": "2-3 days",
    "cost_estimate": 500,
    "benefits": ["benefit1", "benefit2"],
    "drawbacks": ["drawback1"],
    "risk_level": "MEDIUM"
  }
]
"""
        return prompt

    def _parse_solutions(self, response_text: str) -> List[SolutionProposal]:
        """Parse solutions from JSON response"""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if not json_match:
                logger.warning("No JSON array found in response")
                return []

            data = json.loads(json_match.group())
            solutions = []

            for sol_data in data:
                sol = SolutionProposal(
                    problem_statement=sol_data.get("problem_statement", ""),
                    solution_description=sol_data.get("solution_description", ""),
                    confidence=float(sol_data.get("confidence", 0.5)),
                    effort_estimate=sol_data.get("effort_estimate", "Unknown"),
                    cost_estimate=self._safe_float(sol_data.get("cost_estimate", 0)),
                    benefits=sol_data.get("benefits", []),
                    drawbacks=sol_data.get("drawbacks", []),
                    risk_level=sol_data.get("risk_level", "MEDIUM"),
                    category=sol_data.get("category", "IMPLEMENTATION"),
                )
                solutions.append(sol)

            return solutions
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse solutions: {e}")
            return []

    def _safe_float(self, value) -> float:
        """Safely convert value to float"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                # Try to extract number from string like "1-4 weeks"
                import re
                match = re.search(r'\d+', value)
                return float(match.group()) if match else 0.0
            return 0.0
        except:
            return 0.0

    def _select_worker_models(self) -> List[str]:
        """Select worker models based on tier"""
        tier = self.stage_config.worker_tier
        num_workers = self.stage_config.workers

        if tier == "cheap":
            return ["claude-haiku-4-5"] * num_workers
        elif tier == "balanced":
            return ["claude-sonnet-5-5"] * num_workers
        else:  # expensive
            return ["claude-opus-5-5"] * num_workers
