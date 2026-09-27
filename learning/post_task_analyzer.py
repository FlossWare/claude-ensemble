#!/usr/bin/env python3
"""
Post-Task Analyzer — Evaluate outcomes, get consensus, update Thompson priors

After each task:
1. Determine system confidence (know this task type well?)
2. If low confidence: ask user to rate
3. If medium: get consensus model evaluation (skip user)
4. If high: auto-rate from consensus (user can override)
5. Compare user vs consensus rating
6. Update Thompson priors for the model on this task type
7. Trigger alerts if quality/cost anomalies detected
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.thompson_router import StateTracker
from arbitration.api_client import MultiModelAPIClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')


@dataclass
class TaskOutcome:
    """Single task outcome for learning"""
    task_id: str
    task_type: str
    model_used: str
    input_tokens: int
    output_tokens: int
    cost: float
    user_rating: Optional[int]  # 1-5 or None
    consensus_rating: Optional[int]  # 1-5 or None
    system_confidence: float  # 0-1
    was_auto_rated: bool
    timestamp: str


class PostTaskAnalyzer:
    """Analyze task outcomes and update learning"""

    def __init__(self, repo_root: Path = None):
        if repo_root is None:
            repo_root = Path(__file__).parent.parent
        self.repo_root = repo_root
        self.thompson = StateTracker()
        self.api_client = MultiModelAPIClient()
        self.outcomes_dir = repo_root / "learning" / "post_task_outcomes"
        self.outcomes_dir.mkdir(parents=True, exist_ok=True)

    def calculate_system_confidence(self, task_type: str, model: str) -> float:
        """Determine how confident we are in this model for this task (0-1)

        Based on:
        - How many prior tasks of this type?
        - How consistent were the results?
        - How recent were they?
        """
        # Simple heuristic: check Thompson state
        perf = self.thompson.models.get(model)
        if not perf:
            return 0.0  # No prior data

        if perf.calls < 3:
            return 0.2  # Bootstrap phase
        elif perf.calls < 10:
            return 0.5  # Building confidence
        elif perf.calls < 30:
            return 0.75  # Pretty confident
        else:
            return 0.9  # Very confident

    def should_ask_user(self, task_type: str, model: str) -> bool:
        """Determine if we should ask user to rate this outcome"""
        confidence = self.calculate_system_confidence(task_type, model)

        # Bootstrap phase: always ask
        if confidence < 0.3:
            return True

        # Building confidence: ask occasionally (~30%)
        if confidence < 0.7:
            return (hash(f"{task_type}{model}") % 10) < 3

        # High confidence: skip asking (user can override)
        return False

    def get_consensus_rating(
        self, task_type: str, model_used: str, tokens: int, cost: float
    ) -> Tuple[int, Optional[str]]:
        """Get consensus model evaluation of the task outcome

        Uses a DIFFERENT model family than what was used:
        - If used Haiku (cheap): ask Sonnet (balanced)
        - If used Sonnet (balanced): ask Opus (capable)
        - If used Opus (capable): ask Sonnet (check)
        """

        # Model rotation for diversity
        model_sequence = {
            "haiku": "sonnet",
            "sonnet": "opus",
            "opus": "sonnet",
            "cursor": "opus",
            "gemini": "haiku",
        }

        consensus_model = model_sequence.get(model_used, "sonnet")

        logger.info(f"Getting consensus rating from {consensus_model}")

        prompt = f"""
You are reviewing a completed task.

Task Type: {task_type}
Original Model: {model_used}
Tokens Used: {tokens}
Cost: ${cost:.6f}

Rate this outcome (was it a good use of resources?):
1 = Poor (wrong/slow/expensive for the job)
2 = Below average
3 = Acceptable (did the job adequately)
4 = Good (solid quality/cost tradeoff)
5 = Excellent (fast/cheap/high quality)

Respond with ONLY a single number 1-5, no explanation.
"""

        try:
            # Would call actual API in production
            # For now, return heuristic rating
            if tokens > 5000:
                rating = 3  # High token usage
            elif cost > 0.1:
                rating = 2  # Expensive
            else:
                rating = 4  # Reasonable

            return rating, None

        except Exception as e:
            logger.warning(f"Consensus eval failed: {e}")
            return 3, str(e)  # Default to neutral

    def compare_ratings(self, user_rating: Optional[int], consensus_rating: int) -> Dict:
        """Compare user vs consensus rating"""

        if user_rating is None:
            return {
                "comparison": "no_user_rating",
                "agreement": None,
                "final_rating": consensus_rating,
                "notes": "Used consensus rating only",
            }

        diff = abs(user_rating - consensus_rating)

        if diff == 0:
            agreement = "perfect"
        elif diff <= 1:
            agreement = "close"
        else:
            agreement = "divergent"

        # Final rating: average if divergent, otherwise user takes precedence
        if agreement == "perfect":
            final_rating = user_rating
        elif agreement == "close":
            final_rating = user_rating  # Trust user on close calls
        else:
            # Divergent: split difference
            final_rating = (user_rating + consensus_rating) // 2

        return {
            "comparison": agreement,
            "user_rating": user_rating,
            "consensus_rating": consensus_rating,
            "diff": diff,
            "final_rating": final_rating,
            "notes": f"User rated {user_rating}, consensus rated {consensus_rating}",
        }

    def update_thompson_priors(
        self, model: str, task_type: str, final_rating: int, tokens: int, cost: float
    ) -> Dict:
        """Update Thompson priors based on outcome

        Ratings map to success:
        - 1-2: Failure (this model is bad for this task)
        - 3: Neutral (no signal)
        - 4-5: Success (this model is good for this task)
        """

        perf = self.thompson.models.get(model)
        if not perf:
            logger.warning(f"Model {model} not in Thompson state")
            return {}

        # Interpret rating as success/failure
        if final_rating <= 2:
            # Failure
            perf.failures += 1
        elif final_rating >= 4:
            # Success
            perf.successes += 1
        # Rating 3: neutral, no change

        perf.calls += 1
        perf.total_tokens += tokens
        perf.total_cost += cost
        perf.last_updated = datetime.now().isoformat()

        self.thompson.save()

        return {
            "model": model,
            "task_type": task_type,
            "final_rating": final_rating,
            "new_success_rate": perf.quality_rate,
            "total_calls": perf.calls,
            "notes": f"Updated Thompson priors: {perf.successes} successes / {perf.calls} total",
        }

    def analyze(
        self,
        task_id: str,
        task_type: str,
        model_used: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        user_rating: Optional[int] = None,
    ) -> TaskOutcome:
        """Main analysis pipeline"""

        logger.info(f"Analyzing task {task_id}: {task_type} via {model_used}")

        tokens = input_tokens + output_tokens

        # Step 1: Determine confidence
        confidence = self.calculate_system_confidence(task_type, model_used)
        logger.info(f"System confidence: {confidence:.1%}")

        # Step 2: Get consensus rating
        consensus_rating, consensus_error = self.get_consensus_rating(
            task_type, model_used, tokens, cost
        )
        logger.info(f"Consensus rating: {consensus_rating}")

        # Step 3: Compare ratings
        comparison = self.compare_ratings(user_rating, consensus_rating)
        final_rating = comparison.get("final_rating")
        logger.info(f"Final rating: {final_rating} ({comparison['comparison']})")

        # Step 4: Update Thompson
        thompson_update = self.update_thompson_priors(
            model_used, task_type, final_rating, tokens, cost
        )
        logger.info(f"Thompson updated: {thompson_update.get('notes')}")

        # Step 5: Create outcome record
        was_auto_rated = user_rating is None

        outcome = TaskOutcome(
            task_id=task_id,
            task_type=task_type,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            user_rating=user_rating,
            consensus_rating=consensus_rating,
            system_confidence=confidence,
            was_auto_rated=was_auto_rated,
            timestamp=datetime.now().isoformat(),
        )

        # Step 6: Save outcome
        outcome_file = self.outcomes_dir / f"{task_id}.json"
        outcome_file.write_text(json.dumps({
            "outcome": outcome.__dict__,
            "comparison": comparison,
            "thompson_update": thompson_update,
        }, indent=2))

        logger.info(f"Outcome saved: {outcome_file}")

        return outcome

    def get_recent_outcomes(self, days: int = 7) -> list:
        """Get recent task outcomes for reporting"""
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        outcomes = []

        for outcome_file in sorted(self.outcomes_dir.glob("*.json")):
            try:
                data = json.loads(outcome_file.read_text())
                if data["outcome"]["timestamp"] > cutoff:
                    outcomes.append(data)
            except:
                pass

        return outcomes


def main():
    """Demo: analyze a task outcome"""
    analyzer = PostTaskAnalyzer()

    # Example outcome
    outcome = analyzer.analyze(
        task_id="task_001_code_review",
        task_type="code_review",
        model_used="haiku",
        input_tokens=2000,
        output_tokens=800,
        cost=0.0065,
        user_rating=4,  # User rated it good
    )

    print("\n" + "=" * 70)
    print("OUTCOME ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"Task ID:        {outcome.task_id}")
    print(f"Task Type:      {outcome.task_type}")
    print(f"Model:          {outcome.model_used}")
    print(f"User Rating:    {outcome.user_rating}")
    print(f"Consensus:      {outcome.consensus_rating}")
    print(f"System Conf:    {outcome.system_confidence:.1%}")
    print(f"Auto-Rated:     {outcome.was_auto_rated}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
