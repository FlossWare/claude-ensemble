#!/usr/bin/env python3
"""
Solve stage arbiter - synthesize and refine solutions
"""

import json
import logging
from typing import List, Optional
from .models import SolutionProposal, SolveArbiterOutput

logger = logging.getLogger(__name__)


class SolveArbiterRunner:
    """Run arbiter to synthesize solutions from workers"""

    def __init__(self, api_client, request, stage_config):
        self.api_client = api_client
        self.request = request
        self.stage_config = stage_config

    def run_arbiter(
        self,
        problems: List[str],
        worker_outputs: List,
        prior_solutions: Optional[List[SolutionProposal]] = None,
    ) -> SolveArbiterOutput:
        """Run arbiter to synthesize worker solutions"""
        if not self.api_client:
            raise RuntimeError("API client required for arbiter")

        # Collect solutions from all workers
        all_worker_solutions = []
        for output in worker_outputs:
            if hasattr(output, 'solutions'):
                all_worker_solutions.extend(output.solutions)

        model = self.stage_config.arbiter_model or "claude-opus-5-5"
        prompt = self._build_arbiter_prompt(
            problems, all_worker_solutions, prior_solutions
        )

        response_text, tokens_used, cost_usd = self.api_client.call_model(
            model, prompt
        )

        # Parse synthesized solutions
        synthesized_solutions = self._parse_solutions(response_text)

        output = SolveArbiterOutput(
            model=model,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            solutions=synthesized_solutions,
            raw_response=response_text,
        )

        logger.info(
            f"Arbiter synthesized {len(synthesized_solutions)} solutions ({tokens_used} tokens)"
        )
        return output

    def _build_arbiter_prompt(
        self, problems: List[str], worker_solutions: List, prior_solutions
    ) -> str:
        """Build prompt for arbiter"""
        prompt = f"""You are a solution architect arbiter. Synthesize the best solutions from worker proposals.

Problems:
{chr(10).join(f'{i+1}. {p}' for i, p in enumerate(problems))}

Worker Proposals:
"""

        for i, sol in enumerate(worker_solutions, 1):
            prompt += f"""
{i}. Problem: {sol.problem_statement}
   Solution: {sol.solution_description}
   Confidence: {sol.confidence}
   Effort: {sol.effort_estimate}
   Risk: {sol.risk_level}
"""

        if prior_solutions:
            prompt += f"""

Prior Stage Solutions (evaluate improvements):
{chr(10).join(f'- {s.solution_description[:80]}' for s in prior_solutions)}
"""

        prompt += """
TASK:
1. Evaluate each proposal
2. Identify the strongest solutions
3. Synthesize hybrid solutions where beneficial
4. Rank by feasibility and impact
5. Provide top 3-5 final solutions

Return JSON array of final solutions:
[
  {
    "problem_statement": "the problem",
    "solution_description": "final synthesized solution",
    "category": "ARCHITECTURAL|ALGORITHMIC|IMPLEMENTATION|...",
    "confidence": 0.90,
    "effort_estimate": "2-3 days",
    "cost_estimate": 500,
    "benefits": ["benefit1", "benefit2"],
    "drawbacks": [],
    "risk_level": "LOW",
    "rationale": "Why this is the best solution"
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
                logger.warning("No JSON array found in arbiter response")
                return []

            data = json.loads(json_match.group())
            solutions = []

            for sol_data in data:
                sol = SolutionProposal(
                    problem_statement=sol_data.get("problem_statement", ""),
                    solution_description=sol_data.get("solution_description", ""),
                    confidence=float(sol_data.get("confidence", 0.5)),
                    effort_estimate=sol_data.get("effort_estimate", "Unknown"),
                    cost_estimate=float(sol_data.get("cost_estimate", 0)),
                    benefits=sol_data.get("benefits", []),
                    drawbacks=sol_data.get("drawbacks", []),
                    risk_level=sol_data.get("risk_level", "MEDIUM"),
                    category=sol_data.get("category", "IMPLEMENTATION"),
                )
                solutions.append(sol)

            return solutions
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse arbiter solutions: {e}")
            return []
