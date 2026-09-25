#!/usr/bin/env python3
"""Shared module: fetch real numerical sequences from the REST API and
provide GA-compatible task classes.

Workers never touch PostgreSQL directly — data comes via REST API.

Usage from any experiment:
    from ga_sequence_data import RealLineLengthTask, RealIndentationTask, \
        RealNestingTask, REAL_DATA_TASKS, prefetch_sequences
"""

import os
import sys
import time
import math
import random
import json

import requests

API_BASE = os.environ.get("GA_API_BASE", "http://cabin-laptop-02:5000")

_sequence_cache = []
_cache_time = 0
CACHE_TTL = 300
_LOCAL_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "ga_sequences_local.json")

_context_class = None
_execute_fn = None


def set_context(context_class, execute_fn):
    """Called by experiments to register their own Context/execute."""
    global _context_class, _execute_fn
    _context_class = context_class
    _execute_fn = execute_fn


def _get_context_and_execute():
    """Find SelfAwareContext and execute from the calling experiment."""
    if _context_class and _execute_fn:
        return _context_class, _execute_fn
    for mod_name, mod in sys.modules.items():
        if mod and hasattr(mod, 'SelfAwareContext') and hasattr(mod, 'execute'):
            if mod_name != __name__:
                return mod.SelfAwareContext, mod.execute
    for mod_name, mod in sys.modules.items():
        if mod and hasattr(mod, 'SelfAwareContext'):
            exe = getattr(mod, 'execute', None) or getattr(mod, 'execute_tree', None)
            if exe and mod_name != __name__:
                return mod.SelfAwareContext, exe
    raise RuntimeError("No SelfAwareContext/execute found in loaded modules")


def prefetch_sequences(api_base=None, size=200, file_type="sourcecode"):
    """Fetch a batch of real sequences from the API.  Cached for CACHE_TTL
    seconds so experiments don't hammer the endpoint every generation."""
    global _sequence_cache, _cache_time
    if _sequence_cache and (time.time() - _cache_time) < CACHE_TTL:
        return _sequence_cache

    base = api_base or API_BASE
    for attempt in range(3):
        try:
            resp = requests.get(
                f"{base}/sequences/batch",
                params={"type": file_type, "size": size, "random": "true"},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            _sequence_cache = data.get("batch", [])
            _cache_time = time.time()
            try:
                with open(_LOCAL_CACHE_FILE, 'w') as f:
                    json.dump(data, f)
            except OSError:
                pass
            return _sequence_cache
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  [ga_sequence_data] fetch error (attempt {attempt+1}): {e}",
                  file=sys.stderr)
            time.sleep(wait)

    if _sequence_cache:
        print("  [ga_sequence_data] using stale cache", file=sys.stderr)
        return _sequence_cache

    if os.path.exists(_LOCAL_CACHE_FILE):
        try:
            with open(_LOCAL_CACHE_FILE) as f:
                data = json.load(f)
            _sequence_cache = data.get("batch", data if isinstance(data, list) else [])
            _cache_time = time.time()
            print(f"  [ga_sequence_data] loaded {len(_sequence_cache)} sequences from local file",
                  file=sys.stderr)
            return _sequence_cache
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [ga_sequence_data] local file error: {e}", file=sys.stderr)

    return []


def _pick_sequences(n, rng, channel="line_lengths", min_len=10):
    """Pick n sequences from the cache, filtering by minimum length."""
    pool = prefetch_sequences()
    candidates = [s for s in pool
                  if len(s.get(channel, [])) >= min_len]
    if not candidates:
        candidates = pool[:max(1, len(pool))]
    return [rng.choice(candidates) for _ in range(n)]


def _evaluate_prediction(tree, trial, extra_inputs=None):
    """Shared evaluation: feed values through organism, score predictions."""
    Ctx, exe = _get_context_and_execute()
    ctx = Ctx()
    values = trial["values"]
    total_score = 0.0
    warmup = min(5, len(values) // 3)

    base_inputs = [
        trial.get("complexity", 0),
        trial.get("entropy", 0),
    ]
    if extra_inputs:
        base_inputs.extend(extra_inputs)
    while len(base_inputs) < 5:
        base_inputs.append(0)

    for i, val in enumerate(values):
        if i > 0:
            ctx.advance_step()
        ctx.inputs = [val, float(i), float(len(values))] + base_inputs[:5]
        exe(tree, ctx)

        if i >= warmup and i < len(values) - 1:
            prediction = ctx.outputs[0]
            actual_next = values[i + 1]
            error = abs(prediction - actual_next)
            step_score = max(0.0, 1.0 - error)
            total_score += step_score

    scored = max(1, len(values) - warmup - 1)
    return total_score / scored


class RealLineLengthTask:
    """Predict next line length in real source code."""
    name = "real_line_length"

    def generate_trials(self, n, rng):
        seqs = _pick_sequences(n, rng, "line_lengths", min_len=15)
        trials = []
        for seq_data in seqs:
            ll = seq_data.get("line_lengths", [])
            window = min(len(ll), 50)
            start = rng.randint(0, max(0, len(ll) - window))
            segment = ll[start:start + window]
            avg = sum(segment) / max(len(segment), 1)
            scale = max(avg, 1.0)
            trials.append({
                "values": [v / scale for v in segment],
                "raw_values": segment,
                "scale": scale,
                "complexity": seq_data.get("complexity_score", 0),
                "entropy": seq_data.get("entropy", 0),
            })
        return trials

    def evaluate(self, tree, trial, *args, **kwargs):
        return _evaluate_prediction(tree, trial)


class RealIndentationTask:
    """Predict indentation depth patterns in real source code."""
    name = "real_indentation"

    def generate_trials(self, n, rng):
        seqs = _pick_sequences(n, rng, "indentation_depths", min_len=15)
        trials = []
        for seq_data in seqs:
            ind = seq_data.get("indentation_depths", [])
            window = min(len(ind), 50)
            start = rng.randint(0, max(0, len(ind) - window))
            segment = ind[start:start + window]
            max_ind = max(max(segment), 1)
            trials.append({
                "values": [v / max_ind for v in segment],
                "raw_values": segment,
                "max_indent": max_ind,
                "complexity": seq_data.get("complexity_score", 0),
                "entropy": seq_data.get("entropy", 0),
            })
        return trials

    def evaluate(self, tree, trial, *args, **kwargs):
        return _evaluate_prediction(tree, trial,
                                     extra_inputs=[trial["max_indent"] / 20.0])


class RealNestingTask:
    """Track nesting depth changes in real source code."""
    name = "real_nesting"

    def generate_trials(self, n, rng):
        seqs = _pick_sequences(n, rng, "nesting_patterns", min_len=10)
        trials = []
        for seq_data in seqs:
            nest = seq_data.get("nesting_patterns", [])
            window = min(len(nest), 40)
            start = rng.randint(0, max(0, len(nest) - window))
            segment = nest[start:start + window]
            max_d = max(max(segment), 1)
            trials.append({
                "values": [v / max_d for v in segment],
                "raw_values": segment,
                "max_depth": max_d,
                "complexity": seq_data.get("complexity_score", 0),
                "entropy": seq_data.get("entropy", 0),
            })
        return trials

    def evaluate(self, tree, trial, *args, **kwargs):
        return _evaluate_prediction(tree, trial,
                                     extra_inputs=[trial["max_depth"] / 10.0])


REAL_DATA_TASKS = {
    'real_line_length': RealLineLengthTask(),
    'real_indentation': RealIndentationTask(),
    'real_nesting': RealNestingTask(),
}
