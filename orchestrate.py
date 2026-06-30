#!/usr/bin/env python3
"""
Fleet Orchestrator - Runs on aio-01
Distributes tasks to workers and stores results
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from shared.fleet_executor import execute_on_fleet_parallel

def orchestrate_task(task_description, workers=None, model="gpt-4o-mini"):
    """
    Orchestrate a task across the fleet

    Args:
        task_description: The question/task to distribute
        workers: List of worker hostnames (default: all 6 workers)
        model: Model to use (default: gpt-4o-mini)

    Returns:
        List of results from each worker
    """
    if workers is None:
        workers = ["server-01", "server-02", "server-03", "laptop-01", "pi-01", "pi-02"]

    # Create tasks (same task for all workers for consensus)
    tasks = [task_description] * len(workers)

    # Execute on fleet
    results = execute_on_fleet_parallel(
        workers=workers,
        model=model,
        tasks=tasks,
        max_tokens=4000
    )

    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 orchestrate.py '<task_description>' [model]")
        sys.exit(1)

    task = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "gpt-4o-mini"

    print(f"Orchestrating task across fleet: {task[:50]}...")
    results = orchestrate_task(task, model=model)

    # Print results
    for i, r in enumerate(results):
        if "error" in r:
            print(f"Worker {i}: ERROR - {r['error']}")  # Full error
        else:
            print(f"Worker {i}: SUCCESS - {r.get('response', '')[:200]}")
