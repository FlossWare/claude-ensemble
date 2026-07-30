#!/usr/bin/env python3
"""
LinUCB Contextual Bandits for Per-Task Model Routing

Selects the best LLM for a given task based on contextual features
(task type, complexity, domain, query length, etc.) rather than global
win rates.

Complements existing Thompson Sampling (global strategy selection) by
adding per-task intelligence: a code task routes to code-strong models,
a creative task to creative-strong models, etc.

Algorithm: LinUCB (Li et al., 2010)
    For each arm (model) a:
        A_a = d x d matrix (accumulates context outer products + identity)
        b_a = d x 1 vector (accumulates reward-weighted contexts)
        theta_a = A_a^{-1} * b_a (estimated parameter vector)
        UCB_a(x) = theta_a^T x + alpha * sqrt(x^T A_a^{-1} x)

    Select arm with highest UCB.  After observing reward r:
        A_a <- A_a + x x^T
        b_a <- b_a + r * x

Data access: ALL database access goes through REST API at aio-01:5000.
Never connects to PostgreSQL directly.

Usage (CLI):
    # Select best model for a task
    python3 tools/contextual_bandits.py select --task-type code --complexity high --has-code

    # Select with full query text (auto-extracts features)
    python3 tools/contextual_bandits.py select --query "Write a Python function to merge two sorted lists"

    # Show arm performance statistics
    python3 tools/contextual_bandits.py stats

    # List configured arms
    python3 tools/contextual_bandits.py arms

    # Update an arm after observing a reward
    python3 tools/contextual_bandits.py update --model deepseek-chat --reward 0.85 \
        --task-type code --complexity high --has-code

Usage (library):
    from contextual_bandits import (
        LinUCBBandits,
        extract_features,
        select_model,
        update_model,
    )

    # Quick selection via REST API
    model = select_model(query="Implement a binary search tree")

    # Manual control
    bandits = LinUCBBandits.from_api()
    features = extract_features(query="Implement a binary search tree")
    model, ucb = bandits.select(features)
    bandits.update(model, features, reward=0.9)
    bandits.save_to_api()

Created: 2026-07-26
"""

import argparse
import json
import logging
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = "http://aio-01:5000"
REQUEST_TIMEOUT = 10  # seconds

# LinUCB exploration parameter.  Higher = more exploration.
# alpha=1.0 is standard; alpha=0.5 for less exploration after warm-up.
DEFAULT_ALPHA = 1.0

# Feature dimensionality (must match extract_features output length)
FEATURE_DIM = 15

# Regularisation constant for A matrix initialisation (A = lambda * I)
# Larger values shrink theta toward zero, providing more regularisation.
REGULARISATION = 1.0

# Arms: the top models available for routing.
# Each arm is a (name, provider) tuple.  The name is what gets returned
# to the caller; the provider is metadata for display.
DEFAULT_ARMS: List[Dict[str, str]] = [
    # Free tier - strong general purpose
    {"name": "deepseek/deepseek-chat", "provider": "openrouter", "tier": "free"},
    {"name": "qwen/qwen3-235b-a22b:free", "provider": "openrouter", "tier": "free"},
    {"name": "google/gemini-2.5-flash-preview:free", "provider": "openrouter", "tier": "free"},
    {"name": "google/gemini-2.5-pro-preview:free", "provider": "openrouter", "tier": "free"},
    {"name": "nvidia/nemotron-3-ultra-550b-a55b:free", "provider": "openrouter", "tier": "free"},
    {"name": "qwen/qwen3-4b:free", "provider": "openrouter", "tier": "free"},
    {"name": "meta-llama/llama-3.3-70b-instruct:free", "provider": "openrouter", "tier": "free"},
    {"name": "nousresearch/hermes-3-llama-3.1-405b:free", "provider": "openrouter", "tier": "free"},
    {"name": "mistralai/mistral-small-3.2-24b-instruct:free", "provider": "openrouter", "tier": "free"},
    # Free tier - code specialists
    {"name": "qwen/qwen3-coder:free", "provider": "openrouter", "tier": "free"},
    # Paid tier - premium models
    {"name": "claude-sonnet", "provider": "anthropic", "tier": "paid"},
    {"name": "claude-opus", "provider": "anthropic", "tier": "paid"},
    {"name": "claude-haiku", "provider": "anthropic", "tier": "paid"},
]

logger = logging.getLogger(__name__)

# Thread-local RNG for thread safety under Flask/gunicorn
_thread_local = threading.local()


def _get_rng() -> np.random.Generator:
    """Return a thread-local numpy random Generator."""
    if not hasattr(_thread_local, "rng"):
        _thread_local.rng = np.random.default_rng()
    return _thread_local.rng


# ---------------------------------------------------------------------------
# Feature Extraction
# ---------------------------------------------------------------------------

# Task type keywords (order matters for one-hot position)
_TASK_TYPES = {
    "code": ["implement", "write code", "function", "class ", "debug", "refactor",
             "program", "script", "algorithm", " api ", "endpoint", "compile",
             "syntax", " parse ", "deploy", "coding", "codebase", "source code"],
    "math": ["calculate", "solve", "equation", "proof", "theorem", "integral",
             "derivative", "matrix", "linear algebra", "probability", "statistics",
             "optimization"],
    "creative": ["write a story", "poem", "creative", "imagine", "brainstorm",
                 "narrative", "fiction", "dialogue", "compose"],
    "factual": ["what is", "who is", "when did", "where is", "define",
                "explain", "describe", "history of", "tell me about"],
    "analytical": ["analyze", "compare", "evaluate", "assess", "review",
                   "critique", "pros and cons", "trade-off", "investigate"],
    "conversational": ["hello", "hi ", "thanks", "how are you", "chat",
                       "opinion", "think about", "feel about"],
}

# Domain keywords
_DOMAINS = {
    "programming": ["python", "java", "javascript", "typescript", "rust", "go",
                    "c++", "ruby", "sql", "html", "css", "react", "node",
                    "docker", "kubernetes", "git", "api", "database", "linux",
                    "bash", "shell"],
    "science": ["physics", "chemistry", "biology", "neuroscience", "quantum",
                "genetics", "evolution", "climate", "astronomy", "molecule"],
    "specialised": ["legal", "medical", "financial", "compliance", "regulatory",
                    "patent", "contract", "diagnosis", "treatment", "investment",
                    "accounting"],
    # "general" is the fallback -- no keywords needed
}


def extract_features(
    query: str = "",
    task_type: Optional[str] = None,
    complexity: Optional[str] = None,
    domain: Optional[str] = None,
    has_code: Optional[bool] = None,
) -> np.ndarray:
    """Extract a feature vector from a query and/or explicit parameters.

    The feature vector has FEATURE_DIM dimensions:
      [0-5]  Task type one-hot: code, math, creative, factual, analytical, conversational
      [6]    Query length bucket: 0=empty, 0.33=short(<50 words), 0.67=medium, 1.0=long(>200 words)
      [7-9]  Domain one-hot: programming, science, specialised (general = all zeros)
      [10]   Complexity: 0.0=simple, 0.5=moderate, 1.0=complex
      [11]   Has code: 0.0 or 1.0
      [12]   Has question mark: 0.0 or 1.0
      [13]   Has list/enumeration: 0.0 or 1.0
      [14]   Bias term (always 1.0)

    Args:
        query:       Raw query text (features auto-extracted via heuristics).
        task_type:   Override: code|math|creative|factual|analytical|conversational.
        complexity:  Override: simple|moderate|complex.
        domain:      Override: programming|science|specialised|general.
        has_code:    Override: whether query contains code blocks.

    Returns:
        numpy array of shape (FEATURE_DIM,) with float64 values.
    """
    features = np.zeros(FEATURE_DIM, dtype=np.float64)
    query_lower = query.lower().strip() if query else ""
    words = query_lower.split()
    word_count = len(words)

    # --- Task type (dimensions 0-5) ---
    if task_type and task_type in _TASK_TYPES:
        idx = list(_TASK_TYPES.keys()).index(task_type)
        features[idx] = 1.0
    elif query_lower:
        # Auto-detect from keywords -- pick the type with the most keyword hits
        best_type = None
        best_score = 0
        for i, (ttype, keywords) in enumerate(_TASK_TYPES.items()):
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_type = i
        if best_type is not None and best_score > 0:
            features[best_type] = 1.0

    # --- Query length bucket (dimension 6) ---
    if word_count == 0:
        features[6] = 0.0
    elif word_count < 50:
        features[6] = 0.33
    elif word_count <= 200:
        features[6] = 0.67
    else:
        features[6] = 1.0

    # --- Domain (dimensions 7-9) ---
    if domain and domain in _DOMAINS:
        idx = list(_DOMAINS.keys()).index(domain)
        features[7 + idx] = 1.0
    elif domain == "general":
        pass  # all zeros = general
    elif query_lower:
        best_domain = None
        best_score = 0
        for i, (dname, keywords) in enumerate(_DOMAINS.items()):
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_domain = i
        if best_domain is not None and best_score > 0:
            features[7 + best_domain] = 1.0

    # --- Complexity (dimension 10) ---
    if complexity == "simple":
        features[10] = 0.0
    elif complexity == "moderate":
        features[10] = 0.5
    elif complexity == "complex":
        features[10] = 1.0
    elif query_lower:
        # Heuristic: complexity based on length, code blocks, technical terms
        complexity_score = 0.0
        if word_count > 100:
            complexity_score += 0.3
        if word_count > 200:
            complexity_score += 0.2
        if "```" in query:
            complexity_score += 0.2
        technical_terms = ["architecture", "distributed", "concurrent", "recursive",
                           "asynchronous", "optimiz", "parallel", "pipeline",
                           "microservice", "monolith", "scalab"]
        tech_hits = sum(1 for t in technical_terms if t in query_lower)
        complexity_score += min(0.3, tech_hits * 0.1)
        features[10] = min(1.0, complexity_score)

    # --- Has code (dimension 11) ---
    if has_code is not None:
        features[11] = 1.0 if has_code else 0.0
    elif query:
        # Detect code blocks or common code patterns across languages
        code_patterns = (
            r'```'                              # fenced code block
            r'|(?:^|\n)\s*def '                 # Python function
            r'|(?:^|\n)\s*class '               # Python/Java/JS class
            r'|(?:^|\n)\s*import '              # Python/Java import
            r'|(?:^|\n)\s*#include'             # C/C++ include
            r'|(?:^|\n)\s*(?:public|private|protected)\s'  # Java/C# access modifiers
            r'|(?:^|\n)\s*(?:function|const|let|var)\s'    # JavaScript
            r'|(?:^|\n)\s*fn '                  # Rust function
            r'|(?:^|\n)\s*func '                # Go function
            r'|\{[^}]*\}'                       # JSON/brace blocks
            r'|(?:=>|->)\s'                     # arrow functions/returns
            r'|(?:SELECT|INSERT|UPDATE|DELETE)\s.*(?:FROM|INTO|SET|WHERE)'  # SQL
        )
        features[11] = 1.0 if re.search(code_patterns, query, re.IGNORECASE) else 0.0

    # --- Has question mark (dimension 12) ---
    features[12] = 1.0 if "?" in query else 0.0

    # --- Has list/enumeration (dimension 13) ---
    features[13] = 1.0 if re.search(r'(?:^|\n)\s*(?:\d+[.)]\s|[-*]\s)', query) else 0.0

    # --- Bias term (dimension 14) ---
    features[14] = 1.0

    return features


def features_to_dict(features: np.ndarray) -> Dict[str, Any]:
    """Convert a feature vector to a human-readable dictionary."""
    task_types = list(_TASK_TYPES.keys())
    domains = list(_DOMAINS.keys()) + ["general"]

    # Find active task type
    active_task = "unknown"
    for i, tt in enumerate(task_types):
        if i < len(features) and features[i] > 0.5:
            active_task = tt
            break

    # Find active domain
    active_domain = "general"
    for i, d in enumerate(list(_DOMAINS.keys())):
        if 7 + i < len(features) and features[7 + i] > 0.5:
            active_domain = d
            break

    # Length bucket
    length_val = features[6] if len(features) > 6 else 0
    if length_val < 0.1:
        length_label = "empty"
    elif length_val < 0.5:
        length_label = "short"
    elif length_val < 0.8:
        length_label = "medium"
    else:
        length_label = "long"

    # Complexity
    comp_val = features[10] if len(features) > 10 else 0
    if comp_val < 0.25:
        comp_label = "simple"
    elif comp_val < 0.75:
        comp_label = "moderate"
    else:
        comp_label = "complex"

    return {
        "task_type": active_task,
        "query_length": length_label,
        "domain": active_domain,
        "complexity": comp_label,
        "complexity_score": round(float(comp_val), 3),
        "has_code": bool(features[11] > 0.5) if len(features) > 11 else False,
        "has_question": bool(features[12] > 0.5) if len(features) > 12 else False,
        "has_list": bool(features[13] > 0.5) if len(features) > 13 else False,
        "raw_vector": [round(float(x), 4) for x in features],
    }


# ---------------------------------------------------------------------------
# LinUCB Core
# ---------------------------------------------------------------------------

@dataclass
class ArmState:
    """State for a single LinUCB arm (model)."""
    name: str
    provider: str
    tier: str
    A: np.ndarray  # d x d matrix
    b: np.ndarray  # d-dimensional vector
    n_updates: int = 0
    total_reward: float = 0.0
    created_at: str = ""

    def theta(self) -> np.ndarray:
        """Compute the estimated parameter vector theta = A^{-1} b.

        Uses Cholesky decomposition for numerical stability when A is
        well-conditioned, falling back to pseudo-inverse otherwise.
        """
        try:
            # Cholesky is stable for positive-definite A (guaranteed by
            # construction: A = lambda*I + sum of x x^T)
            L = np.linalg.cholesky(self.A)
            # Solve L y = b, then L^T theta = y
            y = np.linalg.solve(L, self.b)
            return np.linalg.solve(L.T, y)
        except np.linalg.LinAlgError:
            # Fallback: pinv for near-singular A (lstsq would give
            # least-squares solution which is not the true inverse)
            return np.linalg.pinv(self.A) @ self.b

    def A_inv(self) -> np.ndarray:
        """Compute A^{-1} for the exploration bonus.

        Uses Cholesky-based inversion for stability, with a pinv fallback.
        """
        try:
            L = np.linalg.cholesky(self.A)
            L_inv = np.linalg.solve(L, np.eye(self.A.shape[0]))
            return L_inv.T @ L_inv
        except np.linalg.LinAlgError:
            return np.linalg.pinv(self.A)

    def predict(self, x: np.ndarray, alpha: float) -> float:
        """Compute the UCB score for context vector x.

        UCB = theta^T x + alpha * sqrt(x^T A^{-1} x)

        Args:
            x:     Context feature vector (d-dimensional).
            alpha: Exploration parameter.

        Returns:
            UCB score (higher = more promising / more uncertain).
        """
        th = self.theta()
        a_inv = self.A_inv()

        expected = float(th @ x)
        # x^T A^{-1} x should always be non-negative for PSD A^{-1}
        exploration_term = float(x @ a_inv @ x)
        # Guard against numerical issues that could make it very slightly negative
        exploration_term = max(0.0, exploration_term)
        bonus = alpha * np.sqrt(exploration_term)

        return expected + bonus

    def update(self, x: np.ndarray, reward: float) -> None:
        """Update arm parameters after observing reward for context x.

        A <- A + x x^T
        b <- b + reward * x

        Args:
            x:      Context feature vector.
            reward: Observed reward in [0, 1].
        """
        self.A = self.A + np.outer(x, x)
        self.b = self.b + reward * x
        self.n_updates += 1
        self.total_reward += reward

    def to_dict(self) -> Dict[str, Any]:
        """Serialise arm state to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "provider": self.provider,
            "tier": self.tier,
            "A": self.A.tolist(),
            "b": self.b.tolist(),
            "n_updates": self.n_updates,
            "total_reward": round(self.total_reward, 6),
            "created_at": self.created_at,
            "avg_reward": round(self.total_reward / self.n_updates, 4) if self.n_updates > 0 else 0.0,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArmState":
        """Deserialise from a dictionary."""
        return cls(
            name=data["name"],
            provider=data.get("provider", "unknown"),
            tier=data.get("tier", "free"),
            A=np.array(data["A"], dtype=np.float64),
            b=np.array(data["b"], dtype=np.float64),
            n_updates=data.get("n_updates", 0),
            total_reward=data.get("total_reward", 0.0),
            created_at=data.get("created_at", ""),
        )

    @classmethod
    def new(cls, name: str, provider: str, tier: str, d: int,
            regularisation: float = REGULARISATION) -> "ArmState":
        """Create a fresh arm with identity-initialised A matrix."""
        return cls(
            name=name,
            provider=provider,
            tier=tier,
            A=regularisation * np.eye(d, dtype=np.float64),
            b=np.zeros(d, dtype=np.float64),
            n_updates=0,
            total_reward=0.0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class LinUCBBandits:
    """LinUCB contextual bandits manager for model routing.

    Thread-safe: uses thread-local RNG and never mutates shared state
    without explicit method calls.
    """

    def __init__(
        self,
        arms: List[ArmState],
        alpha: float = DEFAULT_ALPHA,
        feature_dim: int = FEATURE_DIM,
    ):
        self.arms: Dict[str, ArmState] = {arm.name: arm for arm in arms}
        self.alpha = alpha
        self.feature_dim = feature_dim

    def select(
        self,
        features: np.ndarray,
        candidates: Optional[List[str]] = None,
        tier_filter: Optional[str] = None,
    ) -> Tuple[str, Dict[str, float]]:
        """Select the best arm (model) for the given context.

        Args:
            features:     Context feature vector from extract_features().
            candidates:   Optional list of arm names to restrict selection to.
            tier_filter:  Optional tier filter ("free" or "paid").

        Returns:
            Tuple of (selected_model_name, {model: ucb_score} for all candidates).
        """
        x = np.asarray(features, dtype=np.float64)
        if x.shape[0] != self.feature_dim:
            raise ValueError(
                f"Feature vector has {x.shape[0]} dimensions, "
                f"expected {self.feature_dim}"
            )

        # Determine candidate arms
        eligible = {}
        for name, arm in self.arms.items():
            if candidates and name not in candidates:
                continue
            if tier_filter and arm.tier != tier_filter:
                continue
            eligible[name] = arm

        if not eligible:
            raise ValueError("No eligible arms after filtering")

        # Compute UCB for each arm
        scores: Dict[str, float] = {}
        for name, arm in eligible.items():
            scores[name] = arm.predict(x, self.alpha)

        # Select arm with highest UCB.  Break ties randomly.
        max_score = max(scores.values())
        # Collect all arms within a small epsilon of the max (numerical ties)
        tied = [name for name, s in scores.items() if abs(s - max_score) < 1e-12]
        rng = _get_rng()
        selected = tied[int(rng.integers(len(tied)))] if len(tied) > 1 else tied[0]

        return selected, scores

    def update(self, arm_name: str, features: np.ndarray, reward: float) -> None:
        """Update arm parameters after observing a reward.

        Args:
            arm_name: The model name that was selected.
            features: The context feature vector used for selection.
            reward:   Observed reward, ideally in [0, 1].
        """
        if arm_name not in self.arms:
            raise KeyError(f"Unknown arm: {arm_name}")

        x = np.asarray(features, dtype=np.float64)
        if x.shape[0] != self.feature_dim:
            raise ValueError(
                f"Feature vector has {x.shape[0]} dimensions, "
                f"expected {self.feature_dim}"
            )

        # Clamp reward to [0, 1] to keep A and b in a reasonable range
        reward = max(0.0, min(1.0, float(reward)))
        self.arms[arm_name].update(x, reward)

    def add_arm(self, name: str, provider: str = "unknown",
                tier: str = "free") -> None:
        """Add a new arm dynamically."""
        if name in self.arms:
            logger.warning("Arm %s already exists, skipping", name)
            return
        self.arms[name] = ArmState.new(name, provider, tier, self.feature_dim)

    def stats(self) -> List[Dict[str, Any]]:
        """Return summary statistics for all arms (no state mutation)."""
        result = []
        for name, arm in sorted(self.arms.items()):
            th = arm.theta()
            result.append({
                "name": name,
                "provider": arm.provider,
                "tier": arm.tier,
                "n_updates": arm.n_updates,
                "total_reward": round(arm.total_reward, 4),
                "avg_reward": round(arm.total_reward / arm.n_updates, 4) if arm.n_updates > 0 else 0.0,
                "theta_norm": round(float(np.linalg.norm(th)), 4),
                "A_trace": round(float(np.trace(arm.A)), 4),
                "A_cond": round(float(np.linalg.cond(arm.A)), 2),
                "created_at": arm.created_at,
            })
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Serialise entire bandits state."""
        return {
            "alpha": self.alpha,
            "feature_dim": self.feature_dim,
            "n_arms": len(self.arms),
            "arms": {name: arm.to_dict() for name, arm in self.arms.items()},
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LinUCBBandits":
        """Deserialise from a dictionary."""
        alpha = data.get("alpha", DEFAULT_ALPHA)
        feature_dim = data.get("feature_dim", FEATURE_DIM)
        arms_data = data.get("arms", {})

        arms = []
        for name, arm_dict in arms_data.items():
            arm_dict["name"] = name  # ensure name is set
            arms.append(ArmState.from_dict(arm_dict))

        return cls(arms=arms, alpha=alpha, feature_dim=feature_dim)

    @classmethod
    def new_default(cls, alpha: float = DEFAULT_ALPHA) -> "LinUCBBandits":
        """Create a fresh bandits instance with the default arm set."""
        arms = [
            ArmState.new(a["name"], a["provider"], a["tier"], FEATURE_DIM)
            for a in DEFAULT_ARMS
        ]
        return cls(arms=arms, alpha=alpha, feature_dim=FEATURE_DIM)


# ---------------------------------------------------------------------------
# REST API Interaction
# ---------------------------------------------------------------------------

def _api_get(path: str, api_base: str = API_BASE) -> Optional[Dict]:
    """GET from the REST API, returning parsed JSON or None on error."""
    url = f"{api_base}{path}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        logger.error("Cannot reach API at %s", url)
    except requests.Timeout:
        logger.error("Timeout fetching %s", url)
    except requests.HTTPError as exc:
        logger.error("HTTP error from %s: %s", url, exc)
    except (ValueError, KeyError) as exc:
        logger.error("Failed to parse response from %s: %s", url, exc)
    return None


def _api_post(path: str, body: Dict, api_base: str = API_BASE) -> Optional[Dict]:
    """POST to the REST API, returning parsed JSON or None on error."""
    url = f"{api_base}{path}"
    try:
        resp = requests.post(url, json=body, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        logger.error("Cannot reach API at %s", url)
    except requests.Timeout:
        logger.error("Timeout posting to %s", url)
    except requests.HTTPError as exc:
        logger.error("HTTP error from %s: %s", url, exc)
    except (ValueError, KeyError) as exc:
        logger.error("Failed to parse response from %s: %s", url, exc)
    return None


def select_model(
    query: str = "",
    task_type: Optional[str] = None,
    complexity: Optional[str] = None,
    domain: Optional[str] = None,
    has_code: Optional[bool] = None,
    candidates: Optional[List[str]] = None,
    tier_filter: Optional[str] = None,
    api_base: str = API_BASE,
) -> Optional[str]:
    """High-level: select the best model for a task via the REST API.

    This is the main entry point for callers who just want a model name.

    Args:
        query:       Raw query text.
        task_type:   Override task type.
        complexity:  Override complexity.
        domain:      Override domain.
        has_code:    Override code detection.
        candidates:  Restrict to these model names.
        tier_filter: Restrict to "free" or "paid".
        api_base:    REST API base URL.

    Returns:
        Model name string, or None if selection failed.
    """
    features = extract_features(
        query=query, task_type=task_type, complexity=complexity,
        domain=domain, has_code=has_code,
    )

    body = {
        "features": features.tolist(),
    }
    if candidates:
        body["candidates"] = candidates
    if tier_filter:
        body["tier_filter"] = tier_filter

    result = _api_post("/learning/bandits/select", body, api_base)
    if result and "selected" in result:
        return result["selected"]

    # Fallback: try local selection if API is unreachable
    logger.warning("API selection failed, attempting local fallback")
    try:
        bandits = LinUCBBandits.new_default()
        selected, _ = bandits.select(features, candidates, tier_filter)
        return selected
    except Exception as exc:
        logger.error("Local fallback also failed: %s", exc)
        return None


def update_model(
    model: str,
    reward: float,
    query: str = "",
    task_type: Optional[str] = None,
    complexity: Optional[str] = None,
    domain: Optional[str] = None,
    has_code: Optional[bool] = None,
    api_base: str = API_BASE,
) -> bool:
    """High-level: update arm parameters after observing a reward.

    Args:
        model:   Model name that was used.
        reward:  Observed reward in [0, 1].
        (other): Context features matching the original selection.
        api_base: REST API base URL.

    Returns:
        True if update succeeded, False otherwise.
    """
    features = extract_features(
        query=query, task_type=task_type, complexity=complexity,
        domain=domain, has_code=has_code,
    )

    body = {
        "arm_name": model,
        "features": features.tolist(),
        "reward": max(0.0, min(1.0, float(reward))),
    }

    result = _api_post("/learning/bandits/update", body, api_base)
    return result is not None and result.get("status") == "updated"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LinUCB Contextual Bandits for per-task LLM routing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s select --task-type code --complexity high --has-code
  %(prog)s select --query "Write a Python function to merge sorted lists"
  %(prog)s select --query "What is the capital of France?" --tier free
  %(prog)s update --model deepseek/deepseek-chat --reward 0.9 --task-type code
  %(prog)s stats
  %(prog)s arms
        """,
    )

    sub = parser.add_subparsers(dest="command", help="Action to perform")

    # --- select ---
    sel = sub.add_parser("select", help="Select the best model for a task")
    sel.add_argument("--query", default="", help="Raw query text")
    sel.add_argument("--task-type", choices=list(_TASK_TYPES.keys()),
                     help="Task type override")
    sel.add_argument("--complexity", choices=["simple", "moderate", "complex"],
                     help="Complexity override")
    sel.add_argument("--domain", choices=list(_DOMAINS.keys()) + ["general"],
                     help="Domain override")
    sel.add_argument("--has-code", action="store_true", default=None,
                     help="Query contains code")
    sel.add_argument("--candidates", nargs="+", help="Restrict to these models")
    sel.add_argument("--tier", choices=["free", "paid"], help="Tier filter")
    sel.add_argument("--alpha", type=float, default=DEFAULT_ALPHA,
                     help=f"Exploration parameter (default: {DEFAULT_ALPHA})")
    sel.add_argument("--json", action="store_true", help="JSON output")

    # --- update ---
    upd = sub.add_parser("update", help="Update arm after observing reward")
    upd.add_argument("--model", required=True, help="Model name")
    upd.add_argument("--reward", type=float, required=True,
                     help="Observed reward [0, 1]")
    upd.add_argument("--query", default="", help="Original query text")
    upd.add_argument("--task-type", choices=list(_TASK_TYPES.keys()))
    upd.add_argument("--complexity", choices=["simple", "moderate", "complex"])
    upd.add_argument("--domain", choices=list(_DOMAINS.keys()) + ["general"])
    upd.add_argument("--has-code", action="store_true", default=None)

    # --- stats ---
    st = sub.add_parser("stats", help="Show arm performance statistics")
    st.add_argument("--json", action="store_true", help="JSON output")

    # --- arms ---
    ar = sub.add_parser("arms", help="List configured arms")
    ar.add_argument("--json", action="store_true", help="JSON output")

    # --- features ---
    fe = sub.add_parser("features", help="Extract and display features for a query")
    fe.add_argument("--query", default="", help="Query text to extract features from")
    fe.add_argument("--task-type", choices=list(_TASK_TYPES.keys()))
    fe.add_argument("--complexity", choices=["simple", "moderate", "complex"])
    fe.add_argument("--domain", choices=list(_DOMAINS.keys()) + ["general"])
    fe.add_argument("--has-code", action="store_true", default=None)
    fe.add_argument("--json", action="store_true", help="JSON output")

    parser.add_argument("--api", default=API_BASE,
                        help=f"REST API base URL (default: {API_BASE})")

    return parser


def cmd_select(args) -> int:
    """Select the best model for a task."""
    features = extract_features(
        query=args.query,
        task_type=args.task_type,
        complexity=args.complexity,
        domain=args.domain,
        has_code=args.has_code,
    )

    # Try API first
    body = {"features": features.tolist()}
    if args.candidates:
        body["candidates"] = args.candidates
    if args.tier:
        body["tier_filter"] = args.tier

    result = _api_post("/learning/bandits/select", body, args.api)

    if result and "selected" in result:
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Selected: {result['selected']}")
            if "scores" in result:
                print("\nAll scores:")
                sorted_scores = sorted(result["scores"].items(),
                                       key=lambda kv: kv[1], reverse=True)
                for name, score in sorted_scores[:10]:
                    marker = " <--" if name == result["selected"] else ""
                    print(f"  {name:<50} UCB: {score:>8.4f}{marker}")
            feat_info = features_to_dict(features)
            print(f"\nContext: type={feat_info['task_type']}, "
                  f"domain={feat_info['domain']}, "
                  f"complexity={feat_info['complexity']}, "
                  f"has_code={feat_info['has_code']}")
        return 0

    # Fallback to local
    logger.warning("API unreachable, using local default bandits")
    bandits = LinUCBBandits.new_default(alpha=args.alpha)
    try:
        selected, scores = bandits.select(
            features, args.candidates, args.tier
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    if args.json:
        print(json.dumps({
            "selected": selected,
            "scores": {k: round(v, 6) for k, v in scores.items()},
            "source": "local_fallback",
            "context": features_to_dict(features),
        }, indent=2))
    else:
        print(f"Selected: {selected} (local fallback -- no learned state)")
        feat_info = features_to_dict(features)
        print(f"Context: type={feat_info['task_type']}, "
              f"domain={feat_info['domain']}, "
              f"complexity={feat_info['complexity']}")

    return 0


def cmd_update(args) -> int:
    """Update an arm with observed reward."""
    success = update_model(
        model=args.model,
        reward=args.reward,
        query=args.query,
        task_type=args.task_type,
        complexity=args.complexity,
        domain=args.domain,
        has_code=args.has_code,
        api_base=args.api,
    )

    if success:
        print(f"Updated {args.model} with reward {args.reward:.4f}")
        return 0
    else:
        print(f"Failed to update {args.model} (API may be unreachable)")
        return 1


def cmd_stats(args) -> int:
    """Show arm performance statistics."""
    result = _api_get("/learning/bandits/stats", args.api)

    if result and "arms" in result:
        arms = result["arms"]
        if args.json:
            print(json.dumps(result, indent=2))
            return 0

        print(f"LinUCB Contextual Bandits Statistics")
        print(f"Alpha: {result.get('alpha', '?')} | "
              f"Feature dim: {result.get('feature_dim', '?')} | "
              f"Arms: {len(arms)}")
        print()
        print(f"{'Model':<50} {'Updates':>8} {'Avg Reward':>10} "
              f"{'|theta|':>8} {'tr(A)':>8} {'cond(A)':>10}")
        print("-" * 100)
        for arm in sorted(arms, key=lambda a: a.get("avg_reward", 0), reverse=True):
            print(f"{arm['name']:<50} {arm['n_updates']:>8} "
                  f"{arm['avg_reward']:>10.4f} "
                  f"{arm.get('theta_norm', 0):>8.2f} "
                  f"{arm.get('A_trace', 0):>8.1f} "
                  f"{arm.get('A_cond', 0):>10.1f}")
        return 0

    # Fallback
    print("Cannot fetch stats from API (may be unreachable)")
    return 1


def cmd_arms(args) -> int:
    """List configured arms."""
    result = _api_get("/learning/bandits/arms", args.api)

    if result and "arms" in result:
        arms = result["arms"]
        if args.json:
            print(json.dumps(result, indent=2))
            return 0

        print(f"Configured Arms ({len(arms)})")
        print()
        print(f"{'Model':<50} {'Provider':<15} {'Tier':<6} {'Updates':>8}")
        print("-" * 85)
        for arm in arms:
            print(f"{arm['name']:<50} {arm.get('provider', '?'):<15} "
                  f"{arm.get('tier', '?'):<6} {arm.get('n_updates', 0):>8}")
        return 0

    # Fallback: show default arms
    print("Cannot fetch arms from API; showing default configuration:")
    print()
    for arm in DEFAULT_ARMS:
        print(f"  {arm['name']:<50} ({arm['provider']}, {arm['tier']})")
    return 0


def cmd_features(args) -> int:
    """Extract and display features for a query."""
    features = extract_features(
        query=args.query,
        task_type=args.task_type,
        complexity=args.complexity,
        domain=args.domain,
        has_code=args.has_code,
    )
    info = features_to_dict(features)

    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print(f"Task type:  {info['task_type']}")
        print(f"Domain:     {info['domain']}")
        print(f"Length:     {info['query_length']}")
        print(f"Complexity: {info['complexity']} ({info['complexity_score']:.3f})")
        print(f"Has code:   {info['has_code']}")
        print(f"Has ?:      {info['has_question']}")
        print(f"Has list:   {info['has_list']}")
        print(f"\nRaw vector ({len(info['raw_vector'])}d):")
        labels = (
            list(_TASK_TYPES.keys())
            + ["query_len"]
            + list(_DOMAINS.keys())
            + ["complexity", "has_code", "has_question", "has_list", "bias"]
        )
        for i, (label, val) in enumerate(zip(labels, info["raw_vector"])):
            if val != 0.0:
                print(f"  [{i:2d}] {label:<20} = {val}")

    return 0


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "select": cmd_select,
        "update": cmd_update,
        "stats": cmd_stats,
        "arms": cmd_arms,
        "features": cmd_features,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
