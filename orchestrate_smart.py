#!/usr/bin/env python3
"""
Smart Fleet Orchestrator - GA + Thompson Sampling Integration
Runs on aio-01 with intelligent model selection

Combines:
1. Auto-Profiler (GA-based exploration for unprofiled models)
2. Contextual Bandit (Thompson Sampling for task-specific model selection)
3. Fleet Executor (distributed execution)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from shared.fleet_executor import execute_on_fleet_parallel
from tools.auto_profiler import AutoProfiler
from tools.contextual_bandit_trainer_v2 import ContextualBandit, extract_context
import json
import time

class SmartOrchestrator:
    """Intelligent orchestrator with GA + Thompson Sampling"""

    def __init__(self, exploration_rate=0.15, adaptive=True):
        """
        exploration_rate: Base probability of using unprofiled model (GA exploration)
        adaptive: If True, adjust exploration based on coverage (30% → 15% → 5%)
        """
        self.profiler = AutoProfiler(exploration_rate=exploration_rate, adaptive=adaptive)

        # Load Thompson Sampling bandit if available
        try:
            self.bandit = ContextualBandit.load(
                os.path.expanduser('~/.claude/learning/contextual_bandit_v2.json')
            )
            print("✅ Loaded Thompson Sampling bandit")
        except:
            print("⚠️  Thompson Sampling bandit not found - using Auto-Profiler only")
            self.bandit = None

        # Load model mapping if available
        try:
            with open(os.path.expanduser('~/.claude/learning/model_mapping.json'), 'r') as f:
                mapping = json.load(f)
                # Handle nested structure: {"model_to_id": {...}}
                model_to_id = mapping.get('model_to_id', mapping)
                self.id_to_model = {v: k for k, v in model_to_id.items()}
                print(f"✅ Loaded model mapping ({len(self.id_to_model)} models)")
        except Exception as e:
            print(f"⚠️  Model mapping error: {e}")
            self.id_to_model = None

    def select_model(self, task_description, task_type='general_qa', workflow_name=''):
        """
        Select best model for task using GA + Thompson Sampling

        Returns: (model_id, selection_method)
        """
        # Strategy 1: If Thompson Sampling available and trained, use it
        if self.bandit and self.id_to_model:
            context = extract_context(task_description, workflow_name)
            model_idx, ucb_scores = self.bandit.select_model(context)

            if model_idx in self.id_to_model:
                model = self.id_to_model[model_idx]
                print(f"🎯 Thompson Sampling selected: {model}")
                return model, 'thompson_sampling'

        # Strategy 2: Fall back to Auto-Profiler (GA-based exploration)
        model, is_exploration = self.profiler.select_model_for_task(task_type)

        if is_exploration:
            print(f"🔍 GA Exploration selected: {model}")
            return model, 'ga_exploration'
        else:
            print(f"✓ Auto-Profiler selected: {model}")
            return model, 'auto_profiler'

    def orchestrate_task(self, task_description, workers=None, task_type='general_qa',
                        workflow_name='', max_tokens=4000):
        """
        Orchestrate task with intelligent model selection

        Args:
            task_description: The question/task to distribute
            workers: List of worker hostnames (default: all 8 workers)
            task_type: Task category for Auto-Profiler
            workflow_name: Workflow name for Thompson Sampling context
            max_tokens: Max tokens per response

        Returns:
            dict with results and metadata
        """
        if workers is None:
            workers = [
                "server-01", "server-02", "server-03",
                "laptop-01",
                "pi-01", "pi-02",
                "desktop-ap", "server-ap"
            ]

        print(f"\n{'='*60}")
        print(f"SMART ORCHESTRATOR")
        print(f"{'='*60}")
        print(f"Task: {task_description[:80]}...")
        print(f"Workers: {len(workers)}")
        print(f"Task Type: {task_type}")
        print()

        # Select model using GA + Thompson Sampling
        start_time = time.time()
        model, selection_method = self.select_model(
            task_description,
            task_type=task_type,
            workflow_name=workflow_name
        )

        if not model:
            print("❌ No model selected - falling back to gpt-4o-mini")
            model = "gpt-4o-mini"
            selection_method = 'fallback'

        print(f"Model: {model} (via {selection_method})")
        print(f"Selection time: {time.time() - start_time:.2f}s")
        print()

        # Create tasks (same task for all workers for consensus)
        tasks = [task_description] * len(workers)

        # Execute on fleet
        print(f"Executing on {len(workers)} workers...")
        exec_start = time.time()

        results = execute_on_fleet_parallel(
            workers=workers,
            model=model,
            tasks=tasks,
            max_tokens=max_tokens
        )

        exec_time = time.time() - exec_start

        # Calculate success rate
        successes = sum(1 for r in results if not r.get('error'))
        success_rate = successes / len(results) if results else 0

        print(f"\n{'='*60}")
        print(f"RESULTS")
        print(f"{'='*60}")
        print(f"Execution time: {exec_time:.2f}s")
        print(f"Success rate: {successes}/{len(results)} ({success_rate*100:.1f}%)")
        print()

        # Record result if using GA exploration
        if selection_method == 'ga_exploration':
            avg_latency = exec_time * 1000 / len(workers)  # ms per worker
            self.profiler.record_result(model, task_type, success_rate, avg_latency)

        return {
            'model': model,
            'selection_method': selection_method,
            'workers': len(workers),
            'successes': successes,
            'failures': len(results) - successes,
            'success_rate': success_rate,
            'execution_time': exec_time,
            'results': results
        }

    def get_status(self):
        """Get orchestrator status"""
        print("\n" + "="*60)
        print("SMART ORCHESTRATOR STATUS")
        print("="*60)

        # Auto-Profiler status
        status = self.profiler.get_status()
        print(f"\n📊 Auto-Profiler (GA):")
        print(f"  Coverage: {status['profiled_models']}/{status['total_models']} ({status['coverage_pct']:.1f}%)")
        print(f"  Avg tests/model: {status['avg_tests_per_model']:.1f}")
        print(f"  By task type:")
        for task, count in status['by_task'].items():
            print(f"    {task}: {count} models")

        # Thompson Sampling status
        if self.bandit and self.id_to_model:
            print(f"\n🎯 Thompson Sampling:")
            print(f"  Models trained: {len(self.id_to_model)}")
            print(f"  Context dimensions: {self.bandit.context_dim}")
            print(f"  Exploration parameter (alpha): {self.bandit.alpha}")
        else:
            print(f"\n🎯 Thompson Sampling: Not loaded")

        print()

    def close(self):
        """Cleanup"""
        self.profiler.close()


def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 orchestrate_smart.py '<task>' [task_type] [workflow_name]")
        print()
        print("Examples:")
        print("  orchestrate_smart.py 'Implement Java parser' code_generation")
        print("  orchestrate_smart.py 'Review security issues' code_review")
        print("  orchestrate_smart.py 'Research firmware methods' research")
        print()
        print("Options:")
        print("  --status : Show orchestrator status")
        sys.exit(1)

    if sys.argv[1] == '--status':
        orch = SmartOrchestrator(exploration_rate=0.15)
        orch.get_status()
        orch.close()
        return

    task = sys.argv[1]
    task_type = sys.argv[2] if len(sys.argv) > 2 else 'general_qa'
    workflow_name = sys.argv[3] if len(sys.argv) > 3 else ''

    # Create orchestrator
    orch = SmartOrchestrator(exploration_rate=0.15)

    # Run task
    result = orch.orchestrate_task(
        task_description=task,
        task_type=task_type,
        workflow_name=workflow_name
    )

    # Print individual results
    for i, r in enumerate(result['results']):
        worker = ["server-01", "server-02", "server-03", "laptop-01",
                  "pi-01", "pi-02", "desktop-ap", "server-ap"][i]

        if r.get('error'):
            print(f"❌ {worker}: {r['error']}")
        else:
            response = r.get('response', '')
            print(f"✓ {worker}: {response[:150]}...")

    print(f"\n{'='*60}")
    print(f"Model: {result['model']} (via {result['selection_method']})")
    print(f"Success: {result['successes']}/{result['workers']} workers")
    print(f"Time: {result['execution_time']:.2f}s")
    print(f"{'='*60}\n")

    orch.close()


if __name__ == "__main__":
    main()
