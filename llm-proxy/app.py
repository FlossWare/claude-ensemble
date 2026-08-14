"""OpenAI-compatible LLM Proxy — routes to multiple providers.

Port 8000: /v1/chat/completions, /health, /stats, /v1/models
Fetches API keys from the local orchestrator at localhost:5000/secrets/
"""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from threading import Lock

import requests as http_requests
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

SECRETS_URL = "http://localhost:5000/secrets"

_key_cache = {}
_key_cache_ts = 0
_stats = defaultdict(lambda: {"calls": 0, "errors": 0, "total_ms": 0})
_stats_lock = Lock()

PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_name": "PERSONAL_GROQ_API_KEY",
        "models": [
            "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
            "llama-3.1-70b-versatile", "gemma2-9b-it",
            "mixtral-8x7b-32768", "llama3-70b-8192", "llama3-8b-8192",
        ],
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "key_name": "PERSONAL_CEREBRAS_API_KEY",
        "models": [
            "llama-3.3-70b", "llama-3.1-8b", "llama-3.1-70b",
            "gpt-oss-120b", "gemma-4-31b", "qwen-3-32b",
        ],
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key_name": "PERSONAL_OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "deepseek": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "key_name": "PERSONAL_DEEPSEEK_API_KEY",
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
    },
    "google": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key_name": "PERSONAL_GOOGLE_API_KEY",
        "models": [
            "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash",
            "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.5-pro",
        ],
    },
    "cohere": {
        "url": "https://api.cohere.com/v2/chat",
        "key_name": "PERSONAL_COHERE_API_KEY",
        "models": ["command-r-plus", "command-r", "command-a-03-2025"],
    },
    "mistral": {
        "url": "https://api.mistral.ai/v1/chat/completions",
        "key_name": "PERSONAL_MISTRAL_API_KEY",
        "models": [
            "mistral-large-latest", "mistral-medium-latest",
            "mistral-small-latest", "open-mistral-nemo",
            "codestral-latest", "ministral-8b-latest",
        ],
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key_name": "PERSONAL_OPENROUTER_API_KEY",
        "models": [],
    },
}

MODEL_TO_PROVIDER = {}
for prov, cfg in PROVIDERS.items():
    for m in cfg["models"]:
        MODEL_TO_PROVIDER[m] = prov


def _get_key(key_name):
    global _key_cache, _key_cache_ts
    if time.time() - _key_cache_ts > 300:
        _key_cache = {}
        _key_cache_ts = time.time()

    if key_name in _key_cache:
        return _key_cache[key_name]

    try:
        resp = http_requests.get(f"{SECRETS_URL}/{key_name}", timeout=5)
        if resp.status_code == 200:
            val = resp.json().get("value", "")
            _key_cache[key_name] = val
            return val
    except Exception as e:
        logger.warning("Failed to fetch key %s: %s", key_name, e)

    return None


def _resolve_provider(model):
    if model in MODEL_TO_PROVIDER:
        return MODEL_TO_PROVIDER[model], model

    if "/" in model:
        return "openrouter", model

    for prov, cfg in PROVIDERS.items():
        if any(model.startswith(m.split("-")[0]) for m in cfg["models"]):
            return prov, model

    return "openrouter", model


def _call_provider(provider, model, messages, max_tokens=4096, temperature=0.7, **kwargs):
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return None, f"Unknown provider: {provider}"

    key = _get_key(cfg["key_name"])
    if not key:
        fallback_keys = [k for k in [
            cfg["key_name"] + "_FLOSSWARE",
            cfg["key_name"] + "_HOTMAIL",
            cfg["key_name"] + "_NCRR",
        ] if _get_key(k)]
        key = _get_key(fallback_keys[0]) if fallback_keys else None

    if not key:
        return None, f"No API key for {provider}"

    headers = {"Content-Type": "application/json"}
    url = cfg["url"]
    headers["Authorization"] = f"Bearer {key}"

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    body.update({k: v for k, v in kwargs.items() if k not in body})

    start = time.time()
    try:
        resp = http_requests.post(url, headers=headers,
                                  json=body, timeout=120)
        elapsed_ms = int((time.time() - start) * 1000)

        with _stats_lock:
            _stats[provider]["calls"] += 1
            _stats[provider]["total_ms"] += elapsed_ms

        if resp.status_code != 200:
            with _stats_lock:
                _stats[provider]["errors"] += 1
            return None, f"{provider} returned {resp.status_code}: {resp.text[:500]}"

        return resp.json(), None
    except Exception as e:
        with _stats_lock:
            _stats[provider]["errors"] += 1
        return None, str(e)


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.get_json()
    if not data or "messages" not in data:
        return jsonify({"error": {"message": "messages field required"}}), 400

    model = data.get("model", "llama-3.3-70b-versatile")
    messages = data["messages"]
    max_tokens = data.get("max_tokens", 4096)
    temperature = data.get("temperature", 0.7)

    provider, resolved_model = _resolve_provider(model)

    extra = {k: v for k, v in data.items()
             if k not in ("model", "messages", "max_tokens", "temperature")}
    result, error = _call_provider(provider, resolved_model, messages,
                                   max_tokens, temperature, **extra)
    if error:
        return jsonify({"error": {"message": error, "provider": provider, "model": model}}), 502

    return jsonify(result)


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "providers": list(PROVIDERS.keys()),
        "total_models": sum(len(c["models"]) for c in PROVIDERS.values()),
        "timestamp": datetime.utcnow().isoformat(),
    })


@app.route("/stats")
def stats():
    with _stats_lock:
        return jsonify({
            "providers": {k: dict(v) for k, v in _stats.items()},
            "total_calls": sum(v["calls"] for v in _stats.values()),
            "total_errors": sum(v["errors"] for v in _stats.values()),
        })


@app.route("/v1/models")
def list_models():
    models = []
    for prov, cfg in PROVIDERS.items():
        for m in cfg["models"]:
            models.append({
                "id": m,
                "object": "model",
                "owned_by": prov,
                "created": 0,
            })
    return jsonify({"object": "list", "data": models})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
