#!/usr/bin/env python3
"""
Non-stationary Thompson Sampling with Exponential Decay

Extends standard Thompson Sampling (Beta-Bernoulli bandits) to handle
non-stationary environments where model/strategy performance drifts over time.

Problem: Standard Thompson Sampling accumulates alpha/beta counts forever.
A model that was excellent 3 weeks ago but degraded recently still looks
great because hundreds of old successes dominate a few recent failures.

Solution: Two complementary approaches:
  1. Exponential decay: multiply alpha/beta by decay^rounds before sampling,
     so recent observations weigh more heavily.
  2. Sliding window: only consider the last N observations (requires
     per-observation timestamps, approximated here from aggregate stats).

Data access: ALL database access goes through REST API at aio-01:5000.
Never connects to PostgreSQL directly.

Usage (CLI):
    # List strategies with decayed parameters
    python3 tools/nonstationary_thompson_sampling.py list

    # Select a strategy using decayed Thompson Sampling
    python3 tools/nonstationary_thompson_sampling.py select

    # Select with custom decay factor
    python3 tools/nonstationary_thompson_sampling.py select --decay 0.99

    # Select using sliding window (last 50 observations)
    python3 tools/nonstationary_thompson_sampling.py select --window 50

    # Show diagnostics (how much decay affects each strategy)
    python3 tools/nonstationary_thompson_sampling.py diagnostics

Usage (library):
    from nonstationary_thompson_sampling import (
        select_with_decay,
        apply_decay,
        apply_sliding_window,
        fetch_strategies,
        select_strategy_nonstationary,
    )

    # Quick selection via REST API
    winner = select_with_decay(decay=0.995)

    # Manual control
    strategies = fetch_strategies()
    winner = select_strategy_nonstationary(strategies, decay=0.99)

Created: 2026-07-26
"""

import argparse
import json
import logging
import sys
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = "http://aio-01:5000"
DEFAULT_DECAY = 0.995  # Per-round decay factor
DEFAULT_WINDOW = 100   # Sliding window size (observations)
REQUEST_TIMEOUT = 10   # Seconds

# Minimum alpha/beta after decay -- keeps the distribution defined and
# prevents a fully-decayed arm from collapsing to a point mass.
MIN_PARAM = 1.0

logger = logging.getLogger(__name__)

# Thread-local RNG for safe concurrent use under Flask/gunicorn
_thread_local = threading.local()


def _get_rng():
    """Return a thread-local numpy random Generator instance."""
    if not hasattr(_thread_local, "rng"):
        _thread_local.rng = np.random.default_rng()
    return _thread_local.rng


# ---------------------------------------------------------------------------
# Core decay functions
# ---------------------------------------------------------------------------

def apply_decay(
    alpha: float,
    beta: float,
    decay: float = DEFAULT_DECAY,
    rounds: int = 1,
) -> Tuple[float, float]:
    """Apply exponential decay to Beta distribution parameters.

    After *rounds* rounds, effective counts become alpha * decay^rounds.
    A floor of MIN_PARAM (1.0) is enforced so the Beta distribution
    remains proper and equivalent to a uniform prior at minimum.

    Args:
        alpha:  Current success count (>= 1).
        beta:   Current failure count (>= 1).
        decay:  Per-round multiplicative factor in (0, 1].
        rounds: Number of rounds since last decay application.

    Returns:
        (decayed_alpha, decayed_beta)
    """
    if not 0.0 < decay <= 1.0:
        raise ValueError(f"decay must be in (0, 1], got {decay}")
    if rounds < 0:
        raise ValueError(f"rounds must be >= 0, got {rounds}")
    if rounds == 0 or decay == 1.0:
        return (max(MIN_PARAM, alpha), max(MIN_PARAM, beta))

    factor = decay ** rounds
    return (max(MIN_PARAM, alpha * factor), max(MIN_PARAM, beta * factor))


def apply_sliding_window(
    alpha: float,
    beta: float,
    window: int = DEFAULT_WINDOW,
) -> Tuple[float, float]:
    """Approximate a sliding-window view of Beta parameters.

    Without per-observation timestamps we cannot reconstruct the exact
    window.  Instead we scale alpha and beta so that total observations
    (alpha + beta - 2, subtracting the prior) equal at most *window*,
    preserving the observed success rate.

    If total observations already fit inside the window the parameters
    are returned unchanged (minus floor clamping).

    Args:
        alpha:  Current success count (>= 1).
        beta:   Current failure count (>= 1).
        window: Maximum number of effective observations.

    Returns:
        (windowed_alpha, windowed_beta)
    """
    if window <= 0:
        raise ValueError(f"window must be > 0, got {window}")

    # Observations above the prior
    obs_alpha = max(0.0, alpha - MIN_PARAM)
    obs_beta = max(0.0, beta - MIN_PARAM)
    total_obs = obs_alpha + obs_beta

    if total_obs <= window:
        return (max(MIN_PARAM, alpha), max(MIN_PARAM, beta))

    scale = window / total_obs
    return (
        max(MIN_PARAM, MIN_PARAM + obs_alpha * scale),
        max(MIN_PARAM, MIN_PARAM + obs_beta * scale),
    )


def estimate_rounds_since_update(
    last_updated: Optional[str],
    round_interval_hours: float = 6.0,
) -> int:
    """Estimate how many 'rounds' have elapsed since the strategy was last
    updated, assuming one round every *round_interval_hours*.

    Args:
        last_updated: ISO-8601 timestamp string (or None).
        round_interval_hours: How many hours constitute one round.

    Returns:
        Non-negative integer number of rounds elapsed.
    """
    if not last_updated:
        return 0

    try:
        if isinstance(last_updated, str):
            # Handle various timestamp formats from PostgreSQL / REST API
            ts = last_updated.strip()
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                # Naive timestamp -- assume UTC
                dt = dt.replace(tzinfo=timezone.utc)
        elif isinstance(last_updated, datetime):
            dt = last_updated if last_updated.tzinfo else last_updated.replace(tzinfo=timezone.utc)
        else:
            return 0

        now = datetime.now(timezone.utc)
        elapsed_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
        return int(elapsed_hours / round_interval_hours)
    except (ValueError, TypeError) as exc:
        logger.warning(
            "Failed to parse last_updated=%r, treating as 0 rounds: %s",
            last_updated, exc,
        )
        return 0


# ---------------------------------------------------------------------------
# Strategy selection
# ---------------------------------------------------------------------------

def select_strategy_nonstationary(
    strategies: List[Dict],
    decay: float = DEFAULT_DECAY,
    window: Optional[int] = None,
    round_interval_hours: float = 6.0,
) -> Optional[Dict]:
    """Thompson Sampling with exponential decay (and optional sliding window).

    For each strategy, decays alpha/beta based on time since last update,
    optionally applies a sliding window cap, then samples from
    Beta(decayed_alpha, decayed_beta).  Returns the strategy dict with
    the highest sample.

    Args:
        strategies:  List of strategy dicts from the REST API.
        decay:       Per-round decay factor.
        window:      If set, also apply sliding-window capping.
        round_interval_hours: Hours per round for decay calculation.

    Returns:
        The winning strategy dict (with added keys ``decayed_alpha``,
        ``decayed_beta``, ``sample``), or None if the list is empty.
    """
    if not strategies:
        logger.warning("No strategies provided for selection")
        return None

    best_sample = float("-inf")
    best_strategy = None
    rng = _get_rng()

    for s in strategies:
        # Extract alpha/beta -- preserve legitimate 0 (do NOT use ``or 1``)
        raw_alpha = s.get("alpha", s.get("successes"))
        alpha = float(raw_alpha) if raw_alpha is not None else MIN_PARAM
        raw_beta = s.get("beta", s.get("failures"))
        beta_param = float(raw_beta) if raw_beta is not None else MIN_PARAM

        # Clamp raw values to at least MIN_PARAM
        alpha = max(MIN_PARAM, alpha)
        beta_param = max(MIN_PARAM, beta_param)

        # Determine rounds elapsed
        rounds = estimate_rounds_since_update(
            s.get("last_updated"), round_interval_hours
        )

        # Apply exponential decay
        alpha_d, beta_d = apply_decay(alpha, beta_param, decay, rounds)

        # Optionally apply sliding window
        if window is not None:
            alpha_d, beta_d = apply_sliding_window(alpha_d, beta_d, window)

        # Sample from Beta distribution (thread-safe RNG)
        sample = float(rng.beta(alpha_d, beta_d))

        # Guard against NaN from degenerate parameters
        if np.isnan(sample):
            logger.warning(
                "NaN sample for strategy %s (alpha=%.4f, beta=%.4f), skipping",
                s.get("strategy", s.get("name", "?")), alpha_d, beta_d,
            )
            continue

        # Work on a copy to avoid mutating the caller's input dicts
        s_copy = dict(s)
        s_copy["decayed_alpha"] = round(alpha_d, 4)
        s_copy["decayed_beta"] = round(beta_d, 4)
        s_copy["sample"] = round(sample, 6)
        s_copy["decay_rounds"] = rounds

        if sample > best_sample:
            best_sample = sample
            best_strategy = s_copy

    return best_strategy


# ---------------------------------------------------------------------------
# REST API interaction
# ---------------------------------------------------------------------------

def fetch_strategies(api_base: str = API_BASE) -> List[Dict]:
    """Fetch current strategy performance data from the REST API.

    GET {api_base}/learning/strategies

    Returns:
        List of strategy dicts, or empty list on failure.
    """
    url = f"{api_base}/learning/strategies"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # The API may return the list directly or nested under a key
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Common patterns: {"strategies": [...]}, {"data": [...]}
            for key in ("strategies", "data", "results"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Single-strategy response -- wrap in list
            if "strategy" in data:
                return [data]
        logger.warning("Unexpected response shape from %s: %s", url, type(data))
        return []
    except requests.ConnectionError:
        logger.error("Cannot reach API at %s -- is the orchestrator running?", url)
        return []
    except requests.Timeout:
        logger.error("Timeout fetching strategies from %s", url)
        return []
    except requests.HTTPError as exc:
        logger.error("HTTP error from %s: %s", url, exc)
        return []
    except (ValueError, KeyError) as exc:
        logger.error("Failed to parse strategy response: %s", exc)
        return []


def select_with_decay(
    decay: float = DEFAULT_DECAY,
    window: Optional[int] = None,
    api_base: str = API_BASE,
    round_interval_hours: float = 6.0,
) -> Optional[str]:
    """High-level: fetch strategies from REST API and select one with decay.

    This is the main entry point for callers who just want a strategy name.

    Args:
        decay:  Per-round decay factor.
        window: Optional sliding-window cap.
        api_base: REST API base URL.
        round_interval_hours: Hours per round for decay calculation.

    Returns:
        Name of the selected strategy, or None if selection failed.
    """
    strategies = fetch_strategies(api_base)
    if not strategies:
        return None

    winner = select_strategy_nonstationary(
        strategies, decay=decay, window=window,
        round_interval_hours=round_interval_hours,
    )
    if winner is None:
        return None

    return winner.get("strategy", winner.get("name"))


def get_decayed_strategies(
    decay: float = DEFAULT_DECAY,
    window: Optional[int] = None,
    api_base: str = API_BASE,
    round_interval_hours: float = 6.0,
) -> List[Dict]:
    """Fetch strategies and return them annotated with decayed parameters.

    Useful for diagnostics: see how decay affects each strategy without
    performing a selection.

    Returns:
        List of strategy dicts with added ``decayed_alpha``, ``decayed_beta``,
        ``decay_rounds``, and ``effective_mean`` keys.
    """
    strategies = fetch_strategies(api_base)
    if not strategies:
        return []

    result = []
    for s in strategies:
        # Extract alpha/beta -- preserve legitimate 0 (do NOT use ``or 1``)
        raw_alpha = s.get("alpha", s.get("successes"))
        alpha = float(raw_alpha) if raw_alpha is not None else MIN_PARAM
        raw_beta = s.get("beta", s.get("failures"))
        beta_param = float(raw_beta) if raw_beta is not None else MIN_PARAM

        alpha = max(MIN_PARAM, alpha)
        beta_param = max(MIN_PARAM, beta_param)

        rounds = estimate_rounds_since_update(
            s.get("last_updated"), round_interval_hours
        )

        alpha_d, beta_d = apply_decay(alpha, beta_param, decay, rounds)

        if window is not None:
            alpha_d, beta_d = apply_sliding_window(alpha_d, beta_d, window)

        # Work on a copy to avoid mutating the caller's input dicts
        s_copy = dict(s)
        s_copy["decayed_alpha"] = round(alpha_d, 4)
        s_copy["decayed_beta"] = round(beta_d, 4)
        s_copy["decay_rounds"] = rounds
        s_copy["effective_mean"] = round(alpha_d / (alpha_d + beta_d), 4)
        s_copy["original_mean"] = round(alpha / (alpha + beta_param), 4)
        result.append(s_copy)

    # Sort by effective mean descending for readability
    result.sort(key=lambda x: x["effective_mean"], reverse=True)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Non-stationary Thompson Sampling for LLM strategy selection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                         Show strategies with decayed params
  %(prog)s select                       Select a strategy (default decay=0.995)
  %(prog)s select --decay 0.99          Faster decay (more recency bias)
  %(prog)s select --window 50           Sliding window of 50 observations
  %(prog)s select --decay 0.99 --window 50   Both decay and window
  %(prog)s diagnostics                  Show decay impact analysis
        """,
    )

    parser.add_argument(
        "command",
        choices=["list", "select", "diagnostics"],
        help="Action to perform",
    )
    parser.add_argument(
        "--decay",
        type=float,
        default=DEFAULT_DECAY,
        help=f"Exponential decay factor per round (default: {DEFAULT_DECAY})",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=None,
        help="Sliding window size (number of observations)",
    )
    parser.add_argument(
        "--api",
        default=API_BASE,
        help=f"REST API base URL (default: {API_BASE})",
    )
    parser.add_argument(
        "--round-hours",
        type=float,
        default=6.0,
        help="Hours per decay round (default: 6.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=1,
        help="Number of selections to run (for select command, shows distribution)",
    )
    return parser


def cmd_list(args) -> int:
    """List all strategies with decayed parameters."""
    strategies = get_decayed_strategies(
        decay=args.decay,
        window=args.window,
        api_base=args.api,
        round_interval_hours=args.round_hours,
    )

    if not strategies:
        print("No strategies found (API may be unreachable)")
        return 1

    if args.json:
        # default=str handles datetime serialization without mutating dicts
        print(json.dumps(strategies, indent=2, default=str))
        return 0

    # Table output
    print(f"{'Strategy':<30} {'Alpha':>8} {'Beta':>8} {'D.Alpha':>8} {'D.Beta':>8} "
          f"{'Orig Mean':>10} {'Eff Mean':>10} {'Rounds':>7}")
    print("-" * 105)
    for s in strategies:
        name = s.get("strategy", s.get("name", "?"))[:29]
        alpha = s.get("alpha", s.get("successes", "?"))
        beta = s.get("beta", s.get("failures", "?"))
        print(f"{name:<30} {alpha:>8} {beta:>8} "
              f"{s['decayed_alpha']:>8.2f} {s['decayed_beta']:>8.2f} "
              f"{s['original_mean']:>10.4f} {s['effective_mean']:>10.4f} "
              f"{s['decay_rounds']:>7}")

    print(f"\nDecay factor: {args.decay} | "
          f"Window: {args.window or 'none'} | "
          f"Round interval: {args.round_hours}h")
    return 0


def cmd_select(args) -> int:
    """Select a strategy using decayed Thompson Sampling."""
    strategies = fetch_strategies(args.api)
    if not strategies:
        print("No strategies found (API may be unreachable)")
        return 1

    if args.samples == 1:
        winner = select_strategy_nonstationary(
            strategies, decay=args.decay, window=args.window,
            round_interval_hours=args.round_hours,
        )
        if winner is None:
            print("Selection failed")
            return 1

        name = winner.get("strategy", winner.get("name", "?"))
        if args.json:
            # default=str handles datetime serialization without mutating dicts
            print(json.dumps(winner, indent=2, default=str))
        else:
            print(f"Selected: {name}")
            print(f"  Sample: {winner.get('sample', '?')}")
            print(f"  Decayed alpha/beta: {winner.get('decayed_alpha', '?')} / "
                  f"{winner.get('decayed_beta', '?')}")
            print(f"  Decay rounds: {winner.get('decay_rounds', 0)}")
        return 0

    # Multiple samples: show distribution
    from collections import Counter
    counts = Counter()
    for _ in range(args.samples):
        # Re-fetch to avoid mutation issues from annotated keys
        strats = fetch_strategies(args.api)
        w = select_strategy_nonstationary(
            strats, decay=args.decay, window=args.window,
            round_interval_hours=args.round_hours,
        )
        if w:
            counts[w.get("strategy", w.get("name", "?"))] += 1

    if args.json:
        print(json.dumps(dict(counts), indent=2))
    else:
        print(f"Selection distribution ({args.samples} samples):")
        for name, count in counts.most_common():
            pct = count / args.samples * 100
            bar = "#" * int(pct / 2)
            print(f"  {name:<30} {count:>5} ({pct:>5.1f}%) {bar}")

    return 0


def cmd_diagnostics(args) -> int:
    """Show how decay affects each strategy vs stationary baseline."""
    # Get strategies with no decay (decay=1.0) and with decay
    raw = get_decayed_strategies(
        decay=1.0, window=None, api_base=args.api,
        round_interval_hours=args.round_hours,
    )
    decayed = get_decayed_strategies(
        decay=args.decay, window=args.window, api_base=args.api,
        round_interval_hours=args.round_hours,
    )

    if not raw or not decayed:
        print("No strategies found (API may be unreachable)")
        return 1

    # Build lookup by strategy name
    raw_by_name = {
        s.get("strategy", s.get("name", "?")): s for s in raw
    }
    decayed_by_name = {
        s.get("strategy", s.get("name", "?")): s for s in decayed
    }

    if args.json:
        result = []
        for name in raw_by_name:
            r = raw_by_name[name]
            d = decayed_by_name.get(name, {})
            result.append({
                "strategy": name,
                "raw_alpha": r.get("alpha", r.get("successes")),
                "raw_beta": r.get("beta", r.get("failures")),
                "raw_mean": r.get("original_mean"),
                "decayed_alpha": d.get("decayed_alpha"),
                "decayed_beta": d.get("decayed_beta"),
                "decayed_mean": d.get("effective_mean"),
                "mean_shift": round(
                    (d.get("effective_mean", 0) or 0) - (r.get("original_mean", 0) or 0), 4
                ),
                "decay_rounds": d.get("decay_rounds", 0),
            })
        print(json.dumps(result, indent=2, default=str))
        return 0

    print("Decay Impact Analysis")
    print(f"Decay factor: {args.decay} | Window: {args.window or 'none'} | "
          f"Round interval: {args.round_hours}h")
    print()
    print(f"{'Strategy':<30} {'Raw Mean':>9} {'Eff Mean':>9} {'Shift':>7} "
          f"{'Info Loss':>10} {'Rounds':>7}")
    print("-" * 85)

    for name in sorted(raw_by_name.keys()):
        r = raw_by_name[name]
        d = decayed_by_name.get(name, {})

        raw_mean = r.get("original_mean", 0) or 0
        eff_mean = d.get("effective_mean", 0) or 0
        shift = eff_mean - raw_mean

        # Information loss: how much total count was reduced
        raw_a = r.get("alpha", r.get("successes"))
        raw_b = r.get("beta", r.get("failures"))
        raw_total = (float(raw_a) if raw_a is not None else MIN_PARAM) + \
                    (float(raw_b) if raw_b is not None else MIN_PARAM)
        dec_alpha = d.get("decayed_alpha")
        dec_beta = d.get("decayed_beta")
        dec_total = (float(dec_alpha) if dec_alpha is not None else MIN_PARAM) + \
                    (float(dec_beta) if dec_beta is not None else MIN_PARAM)
        info_loss = min(1.0, max(0.0, 1.0 - dec_total / raw_total)) if raw_total > 0 else 0.0

        name_trunc = name[:29]
        print(f"{name_trunc:<30} {raw_mean:>9.4f} {eff_mean:>9.4f} "
              f"{shift:>+7.4f} {info_loss:>9.1%} {d.get('decay_rounds', 0):>7}")

    # Summary
    strategies_with_decay = [
        d for d in decayed
        if d.get("decay_rounds", 0) > 0
    ]
    if strategies_with_decay:
        avg_rounds = np.mean([d["decay_rounds"] for d in strategies_with_decay])
        max_rounds = max(d["decay_rounds"] for d in strategies_with_decay)
        print(f"\nStrategies affected by decay: {len(strategies_with_decay)}/{len(decayed)}")
        print(f"Avg rounds elapsed: {avg_rounds:.1f} | Max: {max_rounds}")
    else:
        print("\nNo strategies have elapsed decay rounds (all recently updated)")

    return 0


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args()

    commands = {
        "list": cmd_list,
        "select": cmd_select,
        "diagnostics": cmd_diagnostics,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
