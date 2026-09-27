#!/usr/bin/env python3
"""
RH API Wrapper — Orchestrate Thompson routing, execution, cost tracking, and learning

Usage:
  # Mode 1: Task-based (arbitration)
  rh-api-wrapper.py --task code-review --input /path/to/code --phases 2

  # Mode 2: Prompt-based (direct)
  rh-api-wrapper.py --prompt "analyze this code" --model auto --context /path

Examples:
  rh-api-wrapper.py --task code-review --input src/api --phases 3
  rh-api-wrapper.py --prompt "security audit src/" --context src/
  rh-api-wrapper.py --prompt "refactor this" --model sonnet --input file.py
"""

import argparse
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from io import StringIO

# Add repo to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.thompson_router import StateTracker
from cost_tracking.logger import CostLogger
from learning.autonomous_learning import AutonomousLearningSystem
from arbitration.orchestrator import ArbitrationOrchestrator
from arbitration.api_client import MultiModelAPIClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RHAPIWrapper:
    """Main wrapper orchestrating model selection, execution, and learning"""

    def __init__(self):
        self.thompson = StateTracker()
        self.cost_logger = CostLogger()
        self.learner = AutonomousLearningSystem()
        self.api_client = MultiModelAPIClient()
        self.start_time = time.time()
        self.task_id = datetime.now().isoformat()

    def select_model(self, task_type: str, required_capability: float = 0.5) -> str:
        """Select model via Thompson sampling"""
        # In real use, would sample from Thompson distribution
        # For now, use Haiku by default (cheapest)
        logger.info(f"Selecting model for {task_type} (capability: {required_capability})")
        return "haiku"  # Default to cheap option

    def execute_task(self, task_type: str, input_data: str, model: str) -> Dict[str, Any]:
        """Execute task using selected model"""
        logger.info(f"Executing {task_type} with {model}")

        # Placeholder: in real use would call actual API
        # For now, return dummy response
        return {
            "status": "success",
            "model": model,
            "result": f"Analysis via {model}",
            "input_tokens": 1000,
            "output_tokens": 500,
        }

    def execute_arbitration(
        self, task_type: str, input_data: str, phases: int
    ) -> Dict[str, Any]:
        """Execute multi-phase arbitration for critical decisions"""
        logger.info(f"Starting {phases}-phase arbitration for {task_type}")

        # Would call ArbitrationOrchestrator in real use
        return {
            "status": "success",
            "task_type": task_type,
            "phases": phases,
            "result": "Consensus verdict from arbitration",
            "input_tokens": 5000,
            "output_tokens": 2000,
        }

    def log_cost(self, result: Dict) -> float:
        """Log API cost"""
        # Use Haiku pricing for now
        input_cost = result.get("input_tokens", 0) * 0.00000125
        output_cost = result.get("output_tokens", 0) * 0.000005
        total_cost = input_cost + output_cost

        self.cost_logger.log_call(
            model=result.get("model", "haiku"),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            cost_usd=total_cost,
            task_name=result.get("task_type", "unknown"),
        )

        return total_cost

    def prompt_for_rating(self, task_info: Dict) -> Optional[int]:
        """Prompt user to rate task outcome (1-5)"""
        print("\n" + "=" * 70)
        print("TASK COMPLETED")
        print("=" * 70)
        print(f"Task:        {task_info.get('task_type', 'N/A')}")
        print(f"Model:       {task_info.get('model', 'N/A')}")
        print(f"Tokens:      {task_info.get('input_tokens', 0)} input, {task_info.get('output_tokens', 0)} output")
        print(f"Cost:        ${task_info.get('cost', 0):.6f}")
        print(f"Time:        {task_info.get('elapsed_seconds', 0):.1f}s")
        print("=" * 70)
        print("\nRate this outcome (1-5, or press Enter to skip):")
        print("  1 = Poor (wrong/slow/expensive)")
        print("  2 = Below average")
        print("  3 = Acceptable (did the job)")
        print("  4 = Good")
        print("  5 = Excellent (fast/cheap/quality)")
        print()

        try:
            rating_str = input("Your rating (1-5): ").strip()
            if not rating_str:
                print("Skipped rating")
                return None
            rating = int(rating_str)
            if 1 <= rating <= 5:
                return rating
            else:
                print("Invalid rating (must be 1-5)")
                return None
        except (ValueError, KeyboardInterrupt):
            print("Skipped rating")
            return None

    def trigger_learning(
        self, task_info: Dict, user_rating: Optional[int]
    ) -> Dict[str, Any]:
        """Trigger post-task analysis and learning"""
        logger.info(f"Triggering learning analysis for {self.task_id}")

        # Record outcome
        outcome = {
            "task_id": self.task_id,
            "task_type": task_info.get("task_type"),
            "model": task_info.get("model"),
            "user_rating": user_rating,
            "tokens": task_info.get("input_tokens", 0) + task_info.get("output_tokens", 0),
            "cost": task_info.get("cost", 0),
            "timestamp": datetime.now().isoformat(),
        }

        # Log outcome
        self.learner.process_task_completion(outcome)

        # Get report
        report = self.learner.get_learning_report()
        logger.info(f"Learning update: {len(report.get('outcomes', []))} outcomes recorded")

        return report

    def run_task(
        self,
        task_type: str,
        input_data: str,
        phases: Optional[int] = None,
        model: str = "auto",
    ) -> Dict[str, Any]:
        """Main entry point: run task with full orchestration"""

        logger.info(f"Starting task: {task_type}")

        # Select model
        if model == "auto":
            model = self.select_model(task_type)

        # Execute
        if phases:
            # Multi-phase arbitration
            result = self.execute_arbitration(task_type, input_data, phases)
        else:
            # Single model execution
            result = self.execute_task(task_type, input_data, model)

        # Add metadata
        result["task_type"] = task_type
        result["model"] = model

        # Log cost
        cost = self.log_cost(result)
        result["cost"] = cost

        # Timing
        elapsed = time.time() - self.start_time
        result["elapsed_seconds"] = elapsed

        # Prompt for rating
        user_rating = self.prompt_for_rating(result)

        # Trigger learning
        learning_result = self.trigger_learning(result, user_rating)
        result["learning"] = learning_result

        return result


def main():
    parser = argparse.ArgumentParser(
        description="RH API Wrapper — Intelligent model routing with learning"
    )

    # Mode selection
    mode_group = parser.add_argument_group("Mode (choose one)")
    mode_exclusive = mode_group.add_mutually_exclusive_group(required=True)
    mode_exclusive.add_argument(
        "--task",
        choices=["code-review", "bug-analysis", "security-audit", "architecture"],
        help="Task-based mode (uses multi-phase arbitration)",
    )
    mode_exclusive.add_argument(
        "--prompt", help="Prompt-based mode (direct execution)"
    )

    # Common options
    parser.add_argument(
        "--input", required=True, help="Input file or directory path"
    )
    parser.add_argument(
        "--context", help="Additional context directory"
    )
    parser.add_argument(
        "--model",
        default="auto",
        choices=["auto", "haiku", "sonnet", "opus", "cursor", "gemini"],
        help="Model to use (default: auto)",
    )

    # Arbitration phases (task mode only)
    parser.add_argument(
        "--phases",
        type=int,
        default=None,
        help="Number of arbitration phases (task mode only)",
    )

    # Verbose
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run wrapper
    wrapper = RHAPIWrapper()

    if args.task:
        task_type = args.task
        phases = args.phases
        logger.info(f"Task mode: {task_type} ({phases or 1} phase(s))")
    else:
        task_type = "prompt"
        phases = None
        logger.info(f"Prompt mode: {args.prompt}")

    # Read input
    try:
        input_file = Path(args.input)
        if input_file.is_file():
            input_data = input_file.read_text()
        elif input_file.is_dir():
            # Summarize directory
            input_data = f"Directory: {input_file}\nFiles: {len(list(input_file.rglob('*')))}"
        else:
            input_data = args.input
    except Exception as e:
        logger.error(f"Failed to read input: {e}")
        sys.exit(1)

    # Execute
    try:
        result = wrapper.run_task(
            task_type=task_type,
            input_data=input_data,
            phases=phases,
            model=args.model,
        )

        # Print result summary
        print("\n" + "=" * 70)
        print("FINAL RESULT")
        print("=" * 70)
        print(f"Status:      {result.get('status', 'unknown')}")
        print(f"Cost:        ${result.get('cost', 0):.6f}")
        print(f"Time:        {result.get('elapsed_seconds', 0):.1f}s")
        print("=" * 70 + "\n")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
