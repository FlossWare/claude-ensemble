#!/usr/bin/env python3
"""GA Experiment 11: Embedding Pipeline Optimizer

Evolves optimal configuration for embedding 4.3M knowledge chunks across
9 free API providers with key rotation (~34 keys total).

Genome: provider allocation per tier, batch sizes, request delays,
key rotation strategy, parallelism level.

Fitness: Real API calls — embeddings/hour minus rate-limit penalties.
Successful embeddings are stored immediately, so evolution does real work.

Providers (all 1024-dim):
  Google     (4 keys, batch ≤100, 60 RPM/key, 1500 RPD/key)
  Jina       (4 keys, batch 100+, 1M tokens/month/key)
  VoyageAI   (4 keys, batch 50+, monthly token quota)
  Cohere     (3 keys, batch 50+, 1K calls/month/key)
  Mistral    (4 keys, batch 16, mistral-embed 1024-dim)
  NVIDIA     (4 keys, batch 50, NV-Embed-QA 1024-dim)
  DeepInfra  (4 keys, batch 50, BGE-M3 1024-dim)
  HuggingFace(4 keys, batch 32, BGE-large-en 1024-dim)
  Cloudflare (3 keys, batch 100, BGE-large-en 1024-dim)

Category tiers from fleet consensus:
  Tier 1 (embed NOW):   ai, stackoverflow, rfc, redis, ...
  Tier 2 (next):        archwiki, gentoo-wiki, arxiv-cv, ...
  Tier 3 (eventually):  ddwrt, thesis-hal, medical, ...
  Tier 4 (skip):        freshtomato, gentoo

Usage:
    python3 ga_exp11_embedding_pipeline.py
    python3 ga_exp11_embedding_pipeline.py --pop-size 12 --generations 30
    python3 ga_exp11_embedding_pipeline.py --trial-chunks 40 --cores 2
    python3 ga_exp11_embedding_pipeline.py --production  # run best config continuously
"""

import argparse
import copy
import json
import math
import os
import random
import signal
import sys
import time
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

# ============================================================================
# CONSTANTS
# ============================================================================

API_BASE = os.environ.get("GA_API_BASE", "http://cabin-laptop-02:5000")

PROVIDER_NAMES = ["google", "jina", "voyageai", "cohere",
                  "mistral", "nvidia", "deepinfra", "huggingface", "cloudflare"]

PROVIDER_CONFIG = {
    "google": {
        "batch_url": "https://generativelanguage.googleapis.com/v1beta/models/"
                     "gemini-embedding-001:batchEmbedContents",
        "max_batch": 100,
        "auth_style": "query_param",
        "rpd_per_key": 1500,
        "rpm_per_key": 60,
    },
    "jina": {
        "url": "https://api.jina.ai/v1/embeddings",
        "max_batch": 100,
        "auth_style": "bearer",
    },
    "voyageai": {
        "url": "https://api.voyageai.com/v1/embeddings",
        "max_batch": 50,
        "auth_style": "bearer",
    },
    "cohere": {
        "url": "https://api.cohere.com/v2/embed",
        "max_batch": 50,
        "auth_style": "bearer",
        "monthly_limit_per_key": 1000,
    },
    "mistral": {
        "url": "https://api.mistral.ai/v1/embeddings",
        "max_batch": 16,
        "auth_style": "bearer",
    },
    "nvidia": {
        "url": "https://integrate.api.nvidia.com/v1/embeddings",
        "max_batch": 50,
        "auth_style": "bearer",
    },
    "deepinfra": {
        "url": "https://api.deepinfra.com/v1/openai/embeddings",
        "max_batch": 50,
        "auth_style": "bearer",
    },
    "huggingface": {
        "url": "https://router.huggingface.co/hf-inference/models/BAAI/bge-large-en-v1.5",
        "max_batch": 32,
        "auth_style": "bearer",
    },
    "cloudflare": {
        "max_batch": 100,
        "auth_style": "bearer",
    },
}

TIER_CATEGORIES = {
    1: ["ai", "stackoverflow", "rfc", "redis", "apache-docs", "terraform",
        "ml", "ga", "arxiv-ai", "devto", "huggingface", "mongodb",
        "algorithms", "splunk"],
    2: ["archwiki", "gentoo-wiki", "arxiv-cv", "arxiv-cl", "mathematics",
        "physics", "electrical-eng", "mit-ocw", "literature", "web-scrape"],
    3: ["ddwrt", "thesis-hal", "thesis-openalex", "medical-pubmed",
        "chemistry", "legal", "pubmed", "infectious-diseases",
        "epidemiology", "webmd"],
}

SKIP_CATEGORIES = {"freshtomato", "gentoo"}
ALL_TIERS = [1, 2, 3]
ROTATION_STRATEGIES = ["round_robin", "lru", "random"]

_shutdown = threading.Event()

# ============================================================================
# REST API ACCESS (all DB operations go through cabin-laptop-02:5000)
# ============================================================================

def _api_get(path, params=None, retries=3):
    """GET from REST API with retry."""
    for attempt in range(retries):
        try:
            resp = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  [api] GET {path} failed: {e}")
                return None


def _api_post(path, data, retries=3):
    """POST to REST API with retry."""
    for attempt in range(retries):
        try:
            resp = requests.post(f"{API_BASE}{path}", json=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  [api] POST {path} failed: {e}")
                return None


def load_api_keys():
    """Load embedding provider API keys via REST API /secrets."""
    key_names = {
        "google": ["GOOGLE_API_KEY", "PERSONAL_GOOGLE_API_KEY",
                    "PERSONAL_GOOGLE_API_KEY_FLOSSWARE",
                    "PERSONAL_GOOGLE_API_KEY_HOTMAIL"],
        "jina": ["PERSONAL_JINA_API_KEY", "PERSONAL_JINA_API_KEY_FLOSSWARE",
                 "PERSONAL_JINA_API_KEY_HOTMAIL", "PERSONAL_JINA_API_KEY_NCRR"],
        "voyageai": ["PERSONAL_VOYAGEAI_API_KEY",
                     "PERSONAL_VOYAGEAI_API_KEY_FLOSSWARE",
                     "PERSONAL_VOYAGEAI_API_KEY_HOTMAIL",
                     "PERSONAL_VOYAGEAI_API_KEY_NCRR"],
        "cohere": ["PERSONAL_COHERE_API_KEY",
                   "PERSONAL_COHERE_API_KEY_FLOSSWARE",
                   "PERSONAL_COHERE_API_KEY_NCRR"],
        "mistral": ["PERSONAL_MISTRAL_API_KEY",
                    "PERSONAL_MISTRAL_API_KEY_FLOSSWARE",
                    "PERSONAL_MISTRAL_API_KEY_HOTMAIL",
                    "PERSONAL_MISTRAL_API_KEY_NCRR"],
        "nvidia": ["PERSONAL_NVIDIA_API_KEY",
                   "PERSONAL_NVIDIA_API_KEY_FLOSSWARE",
                   "PERSONAL_NVIDIA_API_KEY_HOTMAIL",
                   "PERSONAL_NVIDIA_API_KEY_NCRR"],
        "deepinfra": ["PERSONAL_DEEPINFRA_API_KEY",
                      "PERSONAL_DEEPINFRA_API_KEY_FLOSSWARE",
                      "PERSONAL_DEEPINFRA_API_KEY_HOTMAIL",
                      "PERSONAL_DEEPINFRA_API_KEY_NCRR"],
        "huggingface": ["PERSONAL_HUGGINGFACE_API_KEY",
                        "PERSONAL_HUGGINGFACE_API_KEY_FLOSSWARE",
                        "PERSONAL_HUGGINGFACE_API_KEY_HOTMAIL",
                        "PERSONAL_HUGGINGFACE_API_KEY_NCRR"],
        "cloudflare": ["PERSONAL_CLOUDFLARE_API_KEY",
                       "PERSONAL_CLOUDFLARE_API_KEY_FLOSSWARE",
                       "PERSONAL_CLOUDFLARE_API_KEY_HOTMAIL"],
    }
    keys = {p: [] for p in PROVIDER_NAMES}
    for provider, names in key_names.items():
        for name in names:
            result = _api_get(f"/secrets/{name}")
            if result and result.get("value"):
                keys[provider].append(result["value"])

    # Cloudflare needs account IDs paired with API keys
    global _cloudflare_account_id
    _cloudflare_account_id = None
    acct = _api_get("/secrets/PERSONAL_CLOUDFLARE_ACCOUNT_ID")
    if acct and acct.get("value"):
        _cloudflare_account_id = acct["value"]
    elif not keys.get("cloudflare"):
        pass  # no keys anyway
    else:
        print("  cloudflare: WARNING — no account ID, disabling")
        keys["cloudflare"] = []

    for p, k in keys.items():
        print(f"  {p}: {len(k)} keys loaded")
    total = sum(len(k) for k in keys.values())
    print(f"  TOTAL: {total} keys across {sum(1 for k in keys.values() if k)} providers")
    return keys

_cloudflare_account_id = None


def fetch_unembedded_chunks(tier, limit, last_id=0):
    """Fetch chunks needing embeddings via REST API."""
    cats = TIER_CATEGORIES.get(tier, [])
    if not cats:
        return []
    result = _api_post("/knowledge/chunks/unembedded", {
        "categories": cats,
        "last_id": last_id,
        "limit": limit,
    })
    if result and "chunks" in result:
        return result["chunks"]
    return []


def store_embeddings(results):
    """Store embeddings via REST API."""
    if not results:
        return 0
    result = _api_post("/knowledge/embeddings/store", {
        "embeddings": results,
    })
    if result and "stored" in result:
        return result["stored"]
    return 0


# ============================================================================
# PROVIDER API CALLERS
# ============================================================================

def _call_google(texts, api_key):
    """Google Gemini batchEmbedContents — up to 100 texts."""
    url = PROVIDER_CONFIG["google"]["batch_url"] + f"?key={api_key}"
    body = {
        "requests": [
            {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": t[:8000]}]},
                "outputDimensionality": 1024,
            }
            for t in texts
        ]
    }
    resp = requests.post(url, json=body, timeout=90)
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    resp.raise_for_status()
    data = resp.json()
    embeddings = [e["values"] for e in data.get("embeddings", [])]
    return {"status": 200, "embeddings": embeddings}


def _call_jina(texts, api_key):
    """Jina embeddings v3 — up to 100+ texts."""
    resp = requests.post(
        PROVIDER_CONFIG["jina"]["url"],
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"input": [t[:8000] for t in texts],
              "model": "jina-embeddings-v3", "dimensions": 1024},
        timeout=90,
    )
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    resp.raise_for_status()
    data = resp.json()
    embeddings = [d["embedding"] for d in data.get("data", [])]
    return {"status": 200, "embeddings": embeddings}


def _call_voyageai(texts, api_key):
    """VoyageAI voyage-3 — up to 50+ texts."""
    resp = requests.post(
        PROVIDER_CONFIG["voyageai"]["url"],
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"input": [t[:8000] for t in texts], "model": "voyage-3"},
        timeout=90,
    )
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    resp.raise_for_status()
    data = resp.json()
    embeddings = [d["embedding"] for d in data.get("data", [])]
    return {"status": 200, "embeddings": embeddings}


def _call_cohere(texts, api_key):
    """Cohere v2 embed — up to 50+ texts."""
    resp = requests.post(
        PROVIDER_CONFIG["cohere"]["url"],
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={
            "texts": [t[:8000] for t in texts],
            "model": "embed-v4.0",
            "input_type": "search_document",
            "output_dimension": 1024,
            "embedding_types": ["float"],
        },
        timeout=90,
    )
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    resp.raise_for_status()
    data = resp.json()
    floats = data.get("embeddings", {}).get("float", [])
    return {"status": 200, "embeddings": floats}


def _call_mistral(texts, api_key):
    """Mistral mistral-embed — 1024-dim, batch up to 16."""
    resp = requests.post(
        PROVIDER_CONFIG["mistral"]["url"],
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"model": "mistral-embed", "input": [t[:8000] for t in texts]},
        timeout=90,
    )
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    resp.raise_for_status()
    data = resp.json()
    embeddings = [d["embedding"] for d in data.get("data", [])]
    return {"status": 200, "embeddings": embeddings}


def _call_nvidia(texts, api_key):
    """NVIDIA NIM NV-Embed-QA — 1024-dim, OpenAI-compatible."""
    resp = requests.post(
        PROVIDER_CONFIG["nvidia"]["url"],
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"model": "nvidia/nv-embedqa-e5-v5",
              "input": [t[:2048] for t in texts],
              "input_type": "passage",
              "encoding_format": "float"},
        timeout=90,
    )
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    resp.raise_for_status()
    data = resp.json()
    embeddings = [d["embedding"] for d in data.get("data", [])]
    return {"status": 200, "embeddings": embeddings}


def _call_deepinfra(texts, api_key):
    """DeepInfra BGE-M3 — 1024-dim, OpenAI-compatible."""
    resp = requests.post(
        PROVIDER_CONFIG["deepinfra"]["url"],
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"model": "BAAI/bge-m3", "input": [t[:8000] for t in texts]},
        timeout=90,
    )
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    resp.raise_for_status()
    data = resp.json()
    embeddings = [d["embedding"] for d in data.get("data", [])]
    return {"status": 200, "embeddings": embeddings}


def _call_huggingface(texts, api_key):
    """HuggingFace Inference API — BGE-large-en-v1.5, 1024-dim."""
    resp = requests.post(
        PROVIDER_CONFIG["huggingface"]["url"],
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"inputs": [t[:2048] for t in texts],
              "options": {"wait_for_model": True}},
        timeout=120,
    )
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    if resp.status_code == 503:
        return {"status": 429, "embeddings": [], "error": "model_loading"}
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], list) and isinstance(data[0][0], float):
            return {"status": 200, "embeddings": data}
        if isinstance(data[0], list) and isinstance(data[0][0], list):
            embeddings = [row[0] for row in data]
            return {"status": 200, "embeddings": embeddings}
    return {"status": 200, "embeddings": []}


def _call_cloudflare(texts, api_key):
    """Cloudflare Workers AI — BGE-large-en-v1.5, 1024-dim."""
    if not _cloudflare_account_id:
        return {"status": 500, "embeddings": [], "error": "no_account_id"}
    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{_cloudflare_account_id}/ai/run/@cf/baai/bge-large-en-v1.5")
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={"text": [t[:2048] for t in texts]},
        timeout=90,
    )
    if resp.status_code == 429:
        return {"status": 429, "embeddings": [], "error": "rate_limited"}
    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})
    if isinstance(result, dict) and "data" in result:
        embeddings = result["data"]
    elif isinstance(result, list):
        embeddings = result
    else:
        embeddings = []
    return {"status": 200, "embeddings": embeddings}


PROVIDER_CALLERS = {
    "google": _call_google,
    "jina": _call_jina,
    "voyageai": _call_voyageai,
    "cohere": _call_cohere,
    "mistral": _call_mistral,
    "nvidia": _call_nvidia,
    "deepinfra": _call_deepinfra,
    "huggingface": _call_huggingface,
    "cloudflare": _call_cloudflare,
}


# ============================================================================
# KEY ROTATION
# ============================================================================

class KeyRotator:
    """Thread-safe key rotation per provider."""

    def __init__(self, keys_by_provider):
        self._keys = {p: list(k) for p, k in keys_by_provider.items()}
        self._indices = {p: 0 for p in keys_by_provider}
        self._last_used = {p: {k: 0.0 for k in ks}
                           for p, ks in keys_by_provider.items()}
        self._lock = threading.Lock()

    def next_key(self, provider, strategy="round_robin"):
        with self._lock:
            pool = self._keys.get(provider, [])
            if not pool:
                return None
            if strategy == "round_robin":
                idx = self._indices[provider] % len(pool)
                self._indices[provider] = idx + 1
                key = pool[idx]
            elif strategy == "lru":
                key = min(pool, key=lambda k: self._last_used[provider][k])
            else:  # random
                key = random.choice(pool)
            self._last_used[provider][key] = time.time()
            return key


# ============================================================================
# GENOME
# ============================================================================

@dataclass
class EmbeddingConfig:
    """Genome for the embedding pipeline optimizer."""
    tier_providers: Dict[int, List[str]] = field(default_factory=dict)
    batch_sizes: Dict[str, int] = field(default_factory=dict)
    request_delays: Dict[str, float] = field(default_factory=dict)
    key_rotation: Dict[str, str] = field(default_factory=dict)
    parallelism: int = 2
    fitness: Optional[float] = None
    eval_details: Optional[Dict] = None

    def to_dict(self):
        return {
            "tier_providers": self.tier_providers,
            "batch_sizes": self.batch_sizes,
            "request_delays": self.request_delays,
            "key_rotation": self.key_rotation,
            "parallelism": self.parallelism,
        }


def random_config():
    """Generate a random valid EmbeddingConfig."""
    rng = random.Random()
    config = EmbeddingConfig()

    for tier in ALL_TIERS:
        n = rng.randint(2, len(PROVIDER_NAMES))
        config.tier_providers[tier] = rng.sample(PROVIDER_NAMES, n)

    for p in PROVIDER_NAMES:
        mx = PROVIDER_CONFIG[p].get("max_batch", 50)
        config.batch_sizes[p] = rng.randint(max(5, mx // 10), mx)
        config.request_delays[p] = round(rng.uniform(0.3, 5.0), 2)
        config.key_rotation[p] = rng.choice(ROTATION_STRATEGIES)

    config.parallelism = rng.randint(2, 8)
    return config


def crossover(a, b, rng=None):
    """Uniform crossover of two EmbeddingConfig genomes."""
    rng = rng or random.Random()
    child = EmbeddingConfig()

    for tier in ALL_TIERS:
        child.tier_providers[tier] = list(
            rng.choice([a, b]).tier_providers.get(tier, ["google"])
        )

    for p in PROVIDER_NAMES:
        parent = rng.choice([a, b])
        child.batch_sizes[p] = parent.batch_sizes.get(
            p, PROVIDER_CONFIG[p].get("max_batch", 50) // 2
        )
        child.request_delays[p] = rng.choice([a, b]).request_delays.get(p, 1.0)
        child.key_rotation[p] = rng.choice([a, b]).key_rotation.get(p, "round_robin")

    child.parallelism = rng.choice([a.parallelism, b.parallelism])
    return child


def mutate(config, rate=0.3, rng=None):
    """Mutate an EmbeddingConfig in-place."""
    rng = rng or random.Random()

    for tier in ALL_TIERS:
        if rng.random() < rate:
            providers = list(config.tier_providers.get(tier, ["google"]))
            action = rng.choice(["add", "remove", "swap"])
            if action == "add" and len(providers) < len(PROVIDER_NAMES):
                candidates = [p for p in PROVIDER_NAMES if p not in providers]
                if candidates:
                    providers.append(rng.choice(candidates))
            elif action == "remove" and len(providers) > 1:
                providers.pop(rng.randint(0, len(providers) - 1))
            elif action == "swap" and len(providers) >= 1:
                idx = rng.randint(0, len(providers) - 1)
                candidates = [p for p in PROVIDER_NAMES if p not in providers]
                if candidates:
                    providers[idx] = rng.choice(candidates)
            config.tier_providers[tier] = providers

    for p in PROVIDER_NAMES:
        if rng.random() < rate:
            mx = PROVIDER_CONFIG[p].get("max_batch", 50)
            delta = rng.randint(-mx // 5, mx // 5)
            config.batch_sizes[p] = max(5, min(mx, config.batch_sizes.get(p, 25) + delta))

        if rng.random() < rate:
            delta = rng.uniform(-0.5, 0.5)
            config.request_delays[p] = max(
                0.1, round(config.request_delays.get(p, 1.0) + delta, 2)
            )

        if rng.random() < rate:
            config.key_rotation[p] = rng.choice(ROTATION_STRATEGIES)

    if rng.random() < rate:
        config.parallelism = max(1, min(8, config.parallelism + rng.choice([-1, 0, 1])))

    return config


# ============================================================================
# FITNESS EVALUATION
# ============================================================================

def evaluate_config(config, key_rotator, trial_chunks, chunk_pool):
    """Evaluate an EmbeddingConfig by making REAL API calls.

    Fetches chunks from the pool, batches them per the config's allocation,
    calls providers, measures success/failure rates and timing.
    Successful embeddings are returned for storage.

    Args:
        config: EmbeddingConfig genome to evaluate
        key_rotator: KeyRotator instance
        trial_chunks: how many chunks to attempt per tier
        chunk_pool: dict {tier: [chunks]} pre-fetched from DB

    Returns:
        (fitness, details_dict, embeddings_to_store)
    """
    successes = 0
    failures_429 = 0
    failures_other = 0
    latencies = []
    embeddings_out = []
    t_start = time.time()

    for tier in ALL_TIERS:
        providers = config.tier_providers.get(tier, [])
        if not providers:
            continue
        pool = chunk_pool.get(tier, [])
        if not pool:
            continue

        sample = pool[:trial_chunks]

        chunks_per_provider = max(1, len(sample) // len(providers))
        provider_assignments = []
        offset = 0
        for i, prov in enumerate(providers):
            end = offset + chunks_per_provider if i < len(providers) - 1 else len(sample)
            provider_assignments.append((prov, sample[offset:end]))
            offset = end

        def _call_provider(prov, chunks):
            nonlocal successes, failures_429, failures_other
            batch_size = config.batch_sizes.get(prov, 25)
            rotation = config.key_rotation.get(prov, "round_robin")
            delay = config.request_delays.get(prov, 1.0)
            caller = PROVIDER_CALLERS[prov]
            local_embeddings = []

            for i in range(0, len(chunks), batch_size):
                if _shutdown.is_set():
                    break
                batch = chunks[i : i + batch_size]
                texts = [c["content"][:8000] for c in batch]
                key = key_rotator.next_key(prov, rotation)
                if not key:
                    failures_other += len(batch)
                    continue

                t0 = time.time()
                try:
                    result = caller(texts, key)
                    elapsed = time.time() - t0
                    latencies.append(elapsed)

                    if result["status"] == 200 and result["embeddings"]:
                        embs = result["embeddings"]
                        count = min(len(embs), len(batch))
                        for j in range(count):
                            vec = embs[j]
                            if not isinstance(vec, list) or len(vec) < 256:
                                failures_other += 1
                                continue
                            if len(vec) != 1024:
                                vec = vec[:1024] if len(vec) > 1024 else vec + [0.0] * (1024 - len(vec))
                            successes += 1
                            local_embeddings.append({
                                "chunk_id": batch[j]["id"],
                                "model": _model_name(prov),
                                "provider": prov,
                                "embedding": vec,
                            })
                    elif result.get("status") == 429:
                        failures_429 += len(batch)
                    else:
                        failures_other += len(batch)
                except requests.exceptions.Timeout:
                    failures_other += len(batch)
                except requests.exceptions.RequestException:
                    failures_other += len(batch)
                except Exception:
                    failures_other += len(batch)

                if delay > 0 and i + batch_size < len(chunks):
                    time.sleep(delay)

            return local_embeddings

        if config.parallelism > 1 and len(provider_assignments) > 1:
            with ThreadPoolExecutor(max_workers=min(config.parallelism, len(provider_assignments))) as pool_exec:
                futures = {
                    pool_exec.submit(_call_provider, prov, chunks): prov
                    for prov, chunks in provider_assignments
                }
                for future in as_completed(futures):
                    try:
                        embeddings_out.extend(future.result())
                    except Exception:
                        pass
        else:
            for prov, chunks in provider_assignments:
                embeddings_out.extend(_call_provider(prov, chunks))

    elapsed_total = time.time() - t_start
    total_attempted = successes + failures_429 + failures_other

    if total_attempted == 0:
        return 0.0, {"error": "no_attempts"}, []

    success_rate = successes / total_attempted
    error_429_rate = failures_429 / total_attempted
    embeddings_per_hour = (successes / max(0.1, elapsed_total)) * 3600

    tier_coverage = sum(
        1 for t in ALL_TIERS if config.tier_providers.get(t)
    ) / len(ALL_TIERS)

    active_providers = set()
    for t in ALL_TIERS:
        active_providers.update(config.tier_providers.get(t, []))
    provider_diversity = len(active_providers) / len(PROVIDER_NAMES)

    fitness = (
        embeddings_per_hour
        * (1.0 - 2.0 * error_429_rate)
        * (0.5 + 0.5 * tier_coverage)
        * (0.5 + 0.5 * provider_diversity)
    )
    fitness = max(0.0, fitness)

    details = {
        "successes": successes,
        "failures_429": failures_429,
        "failures_other": failures_other,
        "success_rate": round(success_rate, 4),
        "error_429_rate": round(error_429_rate, 4),
        "embeddings_per_hour": round(embeddings_per_hour, 1),
        "elapsed_seconds": round(elapsed_total, 2),
        "avg_latency": round(np.mean(latencies), 3) if latencies else 0,
        "tier_coverage": round(tier_coverage, 2),
    }

    return fitness, details, embeddings_out


def _model_name(provider):
    return {
        "google": "gemini-embedding-001",
        "jina": "jina-embeddings-v3",
        "voyageai": "voyage-3",
        "cohere": "embed-v4.0",
        "mistral": "mistral-embed",
        "nvidia": "nv-embedqa-e5-v5",
        "deepinfra": "bge-m3",
        "huggingface": "bge-large-en-v1.5",
        "cloudflare": "bge-large-en-v1.5",
    }.get(provider, provider)


# ============================================================================
# EVOLUTION
# ============================================================================

def tournament_select(population, k=3, rng=None):
    rng = rng or random.Random()
    candidates = rng.sample(population, min(k, len(population)))
    return max(candidates, key=lambda c: c.fitness or 0.0)


def evolve(args):
    """Main evolution loop."""
    print("=" * 70)
    print("  EXP11: EMBEDDING PIPELINE OPTIMIZER")
    print("=" * 70)
    print(f"  Population:   {args.pop_size}")
    print(f"  Generations:  {args.generations}")
    print(f"  Trial chunks: {args.trial_chunks} per tier")
    print(f"  Elitism:      {args.elitism}")
    print(f"  Tournament:   {args.tournament_size}")
    print(f"  Mutation:     {args.mutation_rate}")
    print(f"  Seed:         {args.seed}")
    print("=" * 70)

    rng = random.Random(args.seed)
    np.random.seed(args.seed)

    print("\n  Loading API keys...")
    api_keys = load_api_keys()
    empty = [p for p in PROVIDER_NAMES if not api_keys.get(p)]
    if empty:
        print(f"  WARNING: No keys for: {empty}", file=sys.stderr)

    key_rotator = KeyRotator(api_keys)

    print("\n  Pre-fetching chunk samples per tier...")
    chunk_pool = {}
    for tier in ALL_TIERS:
        chunks = fetch_unembedded_chunks(tier, limit=args.trial_chunks * args.pop_size * 2)
        chunk_pool[tier] = chunks
        print(f"    Tier {tier}: {len(chunks)} unembedded chunks available")

    if not any(chunk_pool.values()):
        print("  ERROR: No unembedded chunks found. Nothing to do.", file=sys.stderr)
        sys.exit(1)

    print(f"\n  Generating initial population of {args.pop_size}...")
    population = [random_config() for _ in range(args.pop_size)]

    best_ever = None
    best_fitness_ever = 0.0
    total_embedded = 0
    stagnation = 0

    log_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ga_exp11_results.json",
    )

    for gen in range(args.generations):
        if _shutdown.is_set():
            print(f"\n  Shutdown requested at generation {gen}")
            break

        gen_start = time.time()
        print(f"\n  ── Generation {gen + 1}/{args.generations} ──")

        for i, config in enumerate(population):
            if config.fitness is not None:
                continue
            if _shutdown.is_set():
                break

            per_tier = {}
            for tier in ALL_TIERS:
                pool = chunk_pool.get(tier, [])
                if pool:
                    start = (i * args.trial_chunks) % max(1, len(pool) - args.trial_chunks)
                    per_tier[tier] = pool[start : start + args.trial_chunks]

            fitness, details, embeddings = evaluate_config(
                config, key_rotator, args.trial_chunks, per_tier
            )
            config.fitness = fitness
            config.eval_details = details

            if embeddings:
                stored = store_embeddings(embeddings)
                total_embedded += stored
                details["stored"] = stored

            s = details.get("successes", 0)
            e4 = details.get("failures_429", 0)
            print(f"    [{i+1}/{args.pop_size}] fitness={fitness:,.0f}  "
                  f"ok={s} 429={e4} "
                  f"eph={details.get('embeddings_per_hour', 0):,.0f}  "
                  f"stored={details.get('stored', 0)}")

        ranked = sorted(population, key=lambda c: c.fitness or 0.0, reverse=True)
        gen_best = ranked[0]
        gen_best_fit = gen_best.fitness or 0.0

        if gen_best_fit > best_fitness_ever:
            best_fitness_ever = gen_best_fit
            best_ever = copy.deepcopy(gen_best)
            stagnation = 0
        else:
            stagnation += 1

        gen_elapsed = time.time() - gen_start
        avg_fit = np.mean([c.fitness for c in population if c.fitness is not None])
        print(f"  Gen {gen+1} summary: best={gen_best_fit:,.0f}  avg={avg_fit:,.0f}  "
              f"all-time={best_fitness_ever:,.0f}  stagnation={stagnation}  "
              f"total_embedded={total_embedded}  time={gen_elapsed:.1f}s")

        if gen_best.eval_details:
            d = gen_best.eval_details
            print(f"    Best config: providers={gen_best.tier_providers}  "
                  f"parallel={gen_best.parallelism}  "
                  f"batches={gen_best.batch_sizes}")

        _save_checkpoint(gen, best_ever, population, total_embedded, log_path)

        if gen == args.generations - 1:
            break

        # Adaptive mutation: increase when stagnating
        mut_rate = min(0.6, args.mutation_rate + 0.05 * stagnation)

        # Refresh chunk pool every 5 generations
        if (gen + 1) % 5 == 0:
            print("  Refreshing chunk pool...")
            for tier in ALL_TIERS:
                old_ids = {c["id"] for c in chunk_pool.get(tier, [])}
                fresh = fetch_unembedded_chunks(
                    tier, limit=args.trial_chunks * args.pop_size * 2,
                    last_id=max(old_ids) if old_ids else 0,
                )
                if fresh:
                    chunk_pool[tier] = fresh
                    print(f"    Tier {tier}: refreshed {len(fresh)} chunks")

        # Selection + reproduction
        next_gen = []
        for elite in ranked[: args.elitism]:
            child = copy.deepcopy(elite)
            child.fitness = None
            child.eval_details = None
            next_gen.append(child)

        while len(next_gen) < args.pop_size:
            if rng.random() < 0.8:
                p1 = tournament_select(ranked, args.tournament_size, rng)
                p2 = tournament_select(ranked, args.tournament_size, rng)
                child = crossover(p1, p2, rng)
            else:
                child = random_config()
            mutate(child, rate=mut_rate, rng=rng)
            next_gen.append(child)

        population = next_gen

    print("\n" + "=" * 70)
    print("  EVOLUTION COMPLETE")
    print("=" * 70)
    if best_ever:
        print(f"  Best fitness:       {best_fitness_ever:,.0f}")
        print(f"  Total embedded:     {total_embedded}")
        d = best_ever.eval_details or {}
        print(f"  Embeddings/hour:    {d.get('embeddings_per_hour', 0):,.0f}")
        print(f"  Success rate:       {d.get('success_rate', 0):.1%}")
        print(f"  429 error rate:     {d.get('error_429_rate', 0):.1%}")
        print(f"  Best config:")
        print(f"    Tier providers:   {best_ever.tier_providers}")
        print(f"    Batch sizes:      {best_ever.batch_sizes}")
        print(f"    Request delays:   {best_ever.request_delays}")
        print(f"    Key rotation:     {best_ever.key_rotation}")
        print(f"    Parallelism:      {best_ever.parallelism}")
    print("=" * 70)

    if args.production and best_ever:
        print("\n  Switching to PRODUCTION MODE with best config...")
        run_production(best_ever, key_rotator, chunk_pool)

    return best_ever


def _save_checkpoint(gen, best, population, total_embedded, path):
    """Save evolution state to JSON."""
    try:
        data = {
            "generation": gen + 1,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_embedded": total_embedded,
            "best_fitness": best.fitness if best else 0,
            "best_config": best.to_dict() if best else None,
            "best_details": best.eval_details if best else None,
            "population_fitnesses": [
                c.fitness for c in population if c.fitness is not None
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ============================================================================
# PRODUCTION MODE
# ============================================================================

def run_production(config, key_rotator, initial_pool):
    """Run the best config continuously to embed remaining chunks.

    ALWAYS uses ALL 4 providers across ALL tiers to maximize throughput
    and spread load across all 14 API keys from different accounts.
    Per-provider adaptive backoff when 429s are detected.
    """
    print("\n" + "=" * 70)
    print("  PRODUCTION MODE — ALL providers, ALL keys, ALL tiers")
    print("=" * 70)

    prod_config = copy.deepcopy(config)
    for tier in ALL_TIERS:
        prod_config.tier_providers[tier] = list(PROVIDER_NAMES)
    prod_config.parallelism = 8

    provider_backoff = {p: 0.0 for p in PROVIDER_NAMES}
    provider_consecutive_429 = {p: 0 for p in PROVIDER_NAMES}

    print(f"  Tier providers: ALL ({len(PROVIDER_NAMES)} providers)")
    print(f"  Parallelism:    8 (all concurrent)")
    print(f"  Batch sizes:    {prod_config.batch_sizes}")
    print(f"  Base delays:    {prod_config.request_delays}")
    print(f"  Key rotation:   {prod_config.key_rotation}")

    total_stored = 0
    rounds = 0
    last_id_by_tier = {t: 0 for t in ALL_TIERS}

    while not _shutdown.is_set():
        rounds += 1
        t0 = time.time()

        now = time.time()
        active_providers = [
            p for p in PROVIDER_NAMES if provider_backoff[p] <= now
        ]
        if not active_providers:
            wait = min(provider_backoff.values()) - now
            print(f"  All providers in backoff, waiting {wait:.0f}s...")
            time.sleep(min(wait + 1, 30))
            continue

        for tier in ALL_TIERS:
            prod_config.tier_providers[tier] = list(active_providers)

        chunk_pool = {}
        for tier in ALL_TIERS:
            chunks = fetch_unembedded_chunks(
                tier, limit=200, last_id=last_id_by_tier[tier]
            )
            if chunks:
                last_id_by_tier[tier] = chunks[-1]["id"]
            else:
                last_id_by_tier[tier] = 0
                chunks = fetch_unembedded_chunks(tier, limit=200, last_id=0)
                if chunks:
                    last_id_by_tier[tier] = chunks[-1]["id"]
            chunk_pool[tier] = chunks

        remaining = sum(len(v) for v in chunk_pool.values())
        if remaining == 0:
            print("  No more unembedded chunks. Done!")
            break

        _, details, embeddings = evaluate_config(
            prod_config, key_rotator, 200, chunk_pool
        )

        if embeddings:
            stored = store_embeddings(embeddings)
            total_stored += stored
            elapsed = time.time() - t0
            rate = stored / max(0.1, elapsed) * 3600
            providers_str = ",".join(active_providers)
            print(f"  R{rounds}: +{stored} ({total_stored} total)  "
                  f"{rate:,.0f}/hr  429={details.get('failures_429', 0)}  "
                  f"ok={details.get('successes', 0)}  "
                  f"[{providers_str}]  {elapsed:.1f}s")

            for p in PROVIDER_NAMES:
                if p in active_providers and details.get("failures_429", 0) > 0:
                    provider_consecutive_429[p] += 1
                    if provider_consecutive_429[p] >= 3:
                        backoff_secs = min(300, 30 * provider_consecutive_429[p])
                        provider_backoff[p] = time.time() + backoff_secs
                        print(f"    {p}: backing off {backoff_secs}s "
                              f"({provider_consecutive_429[p]} consecutive 429 rounds)")
                else:
                    provider_consecutive_429[p] = 0
        else:
            time.sleep(5)

    print(f"\n  Production complete. Total stored: {total_stored}")


# ============================================================================
# REPORTING
# ============================================================================

def try_report(gen, best, population, total_embedded):
    """Report generation results via ga_result_reporter if available."""
    try:
        from ga_result_reporter import report_generation
        scores = best.eval_details if best else {}
        report_generation(
            experiment_name="exp11_embedding_pipeline",
            generation=gen,
            best_fitness=best.fitness if best else 0,
            scores=scores,
            metadata={
                "total_embedded": total_embedded,
                "best_config": best.to_dict() if best else None,
            },
        )
    except ImportError:
        pass
    except Exception:
        pass


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GA Exp 11: Embedding Pipeline Optimizer"
    )
    parser.add_argument("--pop-size", type=int, default=12)
    parser.add_argument("--generations", type=int, default=30)
    parser.add_argument("--trial-chunks", type=int, default=30,
                        help="chunks per tier per evaluation")
    parser.add_argument("--elitism", type=int, default=2)
    parser.add_argument("--tournament-size", type=int, default=3)
    parser.add_argument("--mutation-rate", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=1111)
    parser.add_argument("--production", action="store_true",
                        help="after evolution, run best config continuously")
    args = parser.parse_args()

    def _signal_handler(sig, frame):
        print("\n  Signal received, finishing current evaluation...")
        _shutdown.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        evolve(args)
    except KeyboardInterrupt:
        print("\n  Interrupted.")
    except Exception as e:
        print(f"\n  FATAL: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
