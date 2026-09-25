#!/usr/bin/env python3
"""Post GA experiment results to the REST API for tracking.

Workers NEVER touch PostgreSQL directly -- all access through REST API.
Uses GA_API_BASE env var (defaults to http://aio-01:5000).
Retry with exponential backoff (3 retries, 1s/2s/4s).
Non-blocking -- if POST fails, log warning but don't stop evolution.
"""

import os
import time
import json
import requests

API_BASE = os.environ.get("GA_API_BASE", "http://aio-01:5000")


def report_generation(experiment_name, generation, best_fitness, scores,
                      best_program_str=None, metadata=None):
    """POST generation results to API. Non-blocking -- logs warning on failure."""
    payload = {
        "name": f"ga-result-{experiment_name}-gen{generation}",
        "description": f"{experiment_name} gen {generation}: fitness={best_fitness:.4f}",
        "memory_type": "project",
        "content": json.dumps({
            "experiment": experiment_name,
            "generation": generation,
            "best_fitness": best_fitness,
            "scores": scores,
            "program_size": len(best_program_str) if best_program_str else 0,
            "timestamp": time.time(),
            **(metadata or {})
        })
    }
    base = API_BASE
    for attempt in range(3):
        try:
            resp = requests.post(f"{base}/learning/memory",
                json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            wait = 2 ** attempt
            print(f"  [reporter] POST failed (attempt {attempt+1}): {e}")
            time.sleep(wait)
    return False
