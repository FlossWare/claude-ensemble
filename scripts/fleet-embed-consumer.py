#!/usr/bin/env python3
"""Fleet embedding consumer — REST API only, zero dependencies beyond stdlib.

Designed to run on fleet workers with no pip installs. Each worker:
1. Fetches API keys from orchestrator
2. Pulls chunks needing embedding via REST API
3. Calls external embedding APIs (NVIDIA, Mistral, OpenRouter, Voyage)
4. Stores results back via REST API

Usage:
    python3 fleet-embed-consumer.py --api http://aio-01:5000 --target chunks
"""
import argparse
import json
import logging
import os
import signal
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error

# Workers may have wrong clocks causing SSL cert validation to fail.
# Create an unverified context for external embedding API calls only.
_nossl = ssl.create_default_context()
_nossl.check_hostname = False
_nossl.verify_mode = ssl.CERT_NONE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('fleet-consumer')

_shutdown = False
TARGET_DIM = 1024
HOSTNAME = socket.gethostname()


def handle_signal(signum, frame):
    global _shutdown
    log.info('Shutdown requested')
    _shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def http_post(url, data, headers=None, timeout=30):
    body = json.dumps(data).encode()
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, method='POST', headers=hdrs)
    ctx = _nossl if 'aio-01' not in url and 'localhost' not in url else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read())


def http_get(url, timeout=15):
    ctx = _nossl if 'aio-01' not in url and 'localhost' not in url else None
    with urllib.request.urlopen(url, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read())


def normalize_dim(embedding, target=TARGET_DIM):
    if len(embedding) == target:
        return embedding
    if len(embedding) > target:
        return embedding[:target]
    return embedding + [0.0] * (target - len(embedding))


def fetch_key(api_base, key_name):
    try:
        resp = http_get(f'{api_base}/secrets/{key_name}')
        return resp.get('value', '')
    except Exception:
        return ''


class Provider:
    def __init__(self, name, batch_size=8):
        self.name = name
        self.batch_size = batch_size
        self.successes = 0
        self.failures = 0
        self.cooldown_until = 0
        self.consecutive_errors = 0

    def is_available(self):
        return time.time() >= self.cooldown_until

    def set_cooldown(self, seconds=60):
        self.cooldown_until = time.time() + seconds

    def embed(self, texts):
        raise NotImplementedError


class NvidiaProvider(Provider):
    def __init__(self, api_key):
        super().__init__('nvidia', batch_size=8)
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        cleaned = [t[:400] if t.strip() else 'empty' for t in texts]
        data = http_post(
            'https://integrate.api.nvidia.com/v1/embeddings',
            {'model': 'nvidia/nv-embedqa-e5-v5',
             'input': cleaned, 'input_type': 'passage',
             'encoding_format': 'float', 'truncate': 'END'},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class MistralProvider(Provider):
    def __init__(self, api_key):
        super().__init__('mistral', batch_size=8)
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post(
            'https://api.mistral.ai/v1/embeddings',
            {'input': texts, 'model': 'mistral-embed'},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class OpenRouterProvider(Provider):
    def __init__(self, api_key):
        super().__init__('openrouter', batch_size=8)
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post(
            'https://openrouter.ai/api/v1/embeddings',
            {'input': texts,
             'model': 'nvidia/llama-nemotron-embed-vl-1b-v2:free',
             'dimensions': TARGET_DIM},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class NvidiaModelProvider(Provider):
    """Generic NVIDIA NIM embedding provider — works with any NVIDIA model."""
    def __init__(self, api_key, model_id, name, batch_size=8):
        super().__init__(name, batch_size=batch_size)
        self.api_key = api_key
        self.model_id = model_id

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        cleaned = [t[:400] if t.strip() else 'empty' for t in texts]
        data = http_post(
            'https://integrate.api.nvidia.com/v1/embeddings',
            {'model': self.model_id,
             'input': cleaned, 'input_type': 'passage',
             'encoding_format': 'float', 'truncate': 'END'},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class OpenRouterNemotronProvider(Provider):
    """OpenRouter nemotron-3-embed-1b:free — 2048-dim, truncated to 1024."""
    def __init__(self, api_key):
        super().__init__('or-nemotron', batch_size=8)
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post(
            'https://openrouter.ai/api/v1/embeddings',
            {'input': texts,
             'model': 'nvidia/nemotron-3-embed-1b:free',
             'dimensions': 2048},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class VoyageProvider(Provider):
    """Generic Voyage AI embedding provider."""
    def __init__(self, api_key, model='voyage-3', name='voyage'):
        super().__init__(name, batch_size=8)
        self.api_key = api_key
        self.model = model

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post(
            'https://api.voyageai.com/v1/embeddings',
            {'input': texts, 'model': self.model},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


def run_provider(provider, batch_url, store_url):
    """Process one batch with one provider. Returns count embedded."""
    try:
        resp = http_post(batch_url, {'batch_size': provider.batch_size})
    except Exception as e:
        log.warning('API fetch error: %s', str(e)[:100])
        return 0

    chunks = resp.get('chunks', [])
    chunks = [c for c in chunks if (c.get('content') or c.get('content_preview', '')).strip()]
    if not chunks:
        return -1  # signal: no work

    ids = [c['id'] for c in chunks]
    texts = [(c.get('content') or c.get('content_preview') or 'empty') for c in chunks]
    texts = [t if t.strip() else 'empty' for t in texts]

    try:
        embeddings = provider.embed(texts)
        store_resp = http_post(store_url, {
            'embeddings': [
                {'id': id_, 'embedding': emb}
                for id_, emb in zip(ids, embeddings)
            ]
        }, timeout=120)
        stored = store_resp.get('updated', 0)
        provider.successes += stored
        provider.consecutive_errors = 0
        return stored
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        if e.code == 429:
            provider.set_cooldown(120)
        else:
            provider.set_cooldown(30)
        provider.failures += 1
        provider.consecutive_errors += 1
        log.warning('%s: HTTP %d — %s', provider.name, e.code, body[:100])
        return 0
    except Exception as e:
        provider.failures += 1
        provider.consecutive_errors += 1
        if provider.consecutive_errors >= 5:
            provider.set_cooldown(300)
        log.warning('%s: %s', provider.name, str(e)[:120])
        return 0


def main():
    parser = argparse.ArgumentParser(description='Fleet embedding consumer')
    parser.add_argument('--api', default='http://aio-01:5000')
    parser.add_argument('--target', default='chunks', choices=['chunks', 'code'])
    args = parser.parse_args()

    if args.target == 'chunks':
        batch_url = f'{args.api}/knowledge/chunks/batch-embed'
        store_url = f'{args.api}/knowledge/chunks/store-embeddings'
    else:
        batch_url = f'{args.api}/documents/batch-embed'
        store_url = f'{args.api}/documents/store-embeddings'

    log.info('Worker %s starting — target=%s api=%s', HOSTNAME, args.target, args.api)

    keys = {
        'nvidia': fetch_key(args.api, 'NVIDIA_API_KEY'),
        'mistral': fetch_key(args.api, 'PERSONAL_MISTRAL_API_KEY'),
        'openrouter': fetch_key(args.api, 'PERSONAL_OPENROUTER_API_KEY'),
        'voyage': fetch_key(args.api, 'PERSONAL_VOYAGEAI_API_KEY'),
    }
    log.info('Keys fetched: %s', ', '.join(k for k, v in keys.items() if v))

    providers = [p for p in [
        NvidiaProvider(keys['nvidia']),
        NvidiaModelProvider(keys['nvidia'], 'nvidia/nv-embed-v1', 'nvidia-v1'),
        NvidiaModelProvider(keys['nvidia'], 'nvidia/nv-embedcode-7b-v1', 'nvidia-code', batch_size=4),
        NvidiaModelProvider(keys['nvidia'], 'nvidia/llama-nemotron-embed-1b-v2', 'nvidia-nemotron-v2'),
        NvidiaModelProvider(keys['nvidia'], 'nvidia/llama-nemotron-embed-vl-1b-v2', 'nvidia-nemotron-vl'),
        NvidiaModelProvider(keys['nvidia'], 'nvidia/nemotron-3-embed-1b', 'nvidia-nemotron-3'),
        MistralProvider(keys['mistral']),
        OpenRouterProvider(keys['openrouter']),
        OpenRouterNemotronProvider(keys['openrouter']),
        VoyageProvider(keys['voyage'], 'voyage-3', 'voyage-3'),
        VoyageProvider(keys['voyage'], 'voyage-4-lite', 'voyage-4-lite'),
        VoyageProvider(keys['voyage'], 'voyage-code-3', 'voyage-code-3'),
    ] if p.is_available()]

    log.info('Active providers: %s', ', '.join(p.name for p in providers))
    if not providers:
        log.error('No providers available!')
        sys.exit(1)

    start_time = time.time()
    total = 0
    empty_rounds = 0
    provider_idx = 0

    while not _shutdown:
        available = [p for p in providers if p.is_available()]
        if not available:
            time.sleep(5)
            continue

        provider = available[provider_idx % len(available)]
        provider_idx += 1

        count = run_provider(provider, batch_url, store_url)
        if count == -1:
            empty_rounds += 1
            if empty_rounds >= 10:
                log.info('No work for 10 rounds, exiting')
                break
            time.sleep(3)
            continue

        empty_rounds = 0
        total += count

        if total > 0 and total % 100 < provider.batch_size:
            elapsed = time.time() - start_time
            rate = total / elapsed if elapsed > 0 else 0
            summary = ', '.join(f'{p.name}:{p.successes}' for p in providers if p.successes > 0)
            log.info('[%s] %d embedded (%.1f/sec) [%s]', HOSTNAME, total, rate, summary)

    elapsed = time.time() - start_time
    log.info('=== %s FINAL: %d embedded in %.0fs (%.1f/sec) ===', HOSTNAME, total, elapsed,
             total / elapsed if elapsed > 0 else 0)
    for p in providers:
        log.info('  %s: %d ok, %d fail', p.name, p.successes, p.failures)


if __name__ == '__main__':
    main()
