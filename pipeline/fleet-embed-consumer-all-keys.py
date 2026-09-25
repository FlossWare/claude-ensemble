#!/usr/bin/env python3
"""Fleet embedding consumer — ALL keys, ALL providers, zero pip dependencies.

Enhanced version that loads every available embedding API key from the
orchestrator and creates a provider instance per key. Rate limits are
per-key, so using all accounts multiplies throughput.

Usage:
    python3 fleet-embed-consumer-all-keys.py --api http://cabin-laptop-02:5000 --target chunks
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

_nossl = ssl.create_default_context()
_nossl.check_hostname = False
_nossl.verify_mode = ssl.CERT_NONE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('fleet-all-keys')

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
    ctx = _nossl if 'localhost' not in url and '127.0.0.1' not in url else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read())


def http_get(url, timeout=15):
    ctx = _nossl if 'localhost' not in url and '127.0.0.1' not in url else None
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


def fetch_all_keys(api_base):
    try:
        resp = http_get(f'{api_base}/secrets/')
        return resp.get('keys', [])
    except Exception:
        return []


# --- Provider classes ---

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
    def __init__(self, api_key, model_id='nvidia/nv-embedqa-e5-v5', name='nvidia', batch_size=8):
        super().__init__(name, batch_size=batch_size)
        self.api_key = api_key
        self.model_id = model_id

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        cleaned = [t[:400] if t.strip() else 'empty' for t in texts]
        data = http_post(
            'https://integrate.api.nvidia.com/v1/embeddings',
            {'model': self.model_id, 'input': cleaned, 'input_type': 'passage',
             'encoding_format': 'float', 'truncate': 'END'},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class GoogleProvider(Provider):
    def __init__(self, api_key, name='google'):
        super().__init__(name, batch_size=1)
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        results = []
        for text in texts:
            data = http_post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={self.api_key}',
                {'content': {'parts': [{'text': text[:2000]}]}, 'outputDimensionality': TARGET_DIM},
            )
            emb = data.get('embedding', {}).get('values', [])
            results.append(normalize_dim(emb))
        return results


class VoyageProvider(Provider):
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


class OpenRouterProvider(Provider):
    def __init__(self, api_key, model='nvidia/llama-nemotron-embed-vl-1b-v2:free', name='openrouter'):
        super().__init__(name, batch_size=8)
        self.api_key = api_key
        self.model = model

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post(
            'https://openrouter.ai/api/v1/embeddings',
            {'input': texts, 'model': self.model, 'dimensions': TARGET_DIM},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class CohereProvider(Provider):
    def __init__(self, api_key, name='cohere'):
        super().__init__(name, batch_size=8)
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post(
            'https://api.cohere.ai/v2/embed',
            {'texts': texts, 'model': 'embed-english-v3.0',
             'input_type': 'search_document', 'embedding_types': ['float']},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        embs = data.get('embeddings', {}).get('float', [])
        return [normalize_dim(e) for e in embs]


class DeepInfraProvider(Provider):
    def __init__(self, api_key, name='deepinfra'):
        super().__init__(name, batch_size=8)
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post(
            'https://api.deepinfra.com/v1/openai/embeddings',
            {'input': texts, 'model': 'BAAI/bge-large-en-v1.5', 'encoding_format': 'float'},
            headers={'Authorization': f'Bearer {self.api_key}'},
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class CloudflareProvider(Provider):
    def __init__(self, api_key, account_id, name='cloudflare'):
        super().__init__(name, batch_size=1)
        self.api_key = api_key
        self.account_id = account_id

    def is_available(self):
        return bool(self.api_key) and bool(self.account_id) and super().is_available()

    def embed(self, texts):
        results = []
        for text in texts:
            data = http_post(
                f'https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/@cf/baai/bge-large-en-v1.5',
                {'text': [text[:2000]]},
                headers={'Authorization': f'Bearer {self.api_key}'},
            )
            d = data.get('result', {}).get('data', [])
            results.append(normalize_dim(d[0]) if d else [0.0] * TARGET_DIM)
        return results


class MistralProvider(Provider):
    def __init__(self, api_key, name='mistral'):
        super().__init__(name, batch_size=8)
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


# --- Provider factory ---

NVIDIA_MODELS = [
    ('nvidia/nv-embedqa-e5-v5', 'nvidia', 8),
    ('nvidia/nv-embed-v1', 'nvidia-v1', 8),
    ('nvidia/llama-nemotron-embed-1b-v2', 'nvidia-nemotron-v2', 8),
    ('nvidia/llama-nemotron-embed-vl-1b-v2', 'nvidia-nemotron-vl', 8),
    ('nvidia/nemotron-3-embed-1b', 'nvidia-nemotron-3', 8),
]

OPENROUTER_MODELS = [
    ('nvidia/llama-nemotron-embed-vl-1b-v2:free', 'or-nemotron-vl'),
    ('nvidia/nemotron-3-embed-1b:free', 'or-nemotron-3'),
]

VOYAGE_MODELS = ['voyage-3', 'voyage-4-lite', 'voyage-code-3']


def build_providers(api_base):
    all_key_names = fetch_all_keys(api_base)
    providers = []

    def get(name):
        return fetch_key(api_base, name)

    cf_account_id = get('PERSONAL_CLOUDFLARE_ACCOUNT_ID')

    key_map = {
        'nvidia': [k for k in all_key_names if 'NVIDIA_API_KEY' in k],
        'google': [k for k in all_key_names if 'GOOGLE_API_KEY' in k and 'CLIENT' not in k and 'password' not in k.lower()],
        'voyage': [k for k in all_key_names if 'VOYAGEAI_API_KEY' in k],
        'openrouter': [k for k in all_key_names if 'OPENROUTER_API_KEY' in k],
        'cohere': [k for k in all_key_names if 'COHERE_API_KEY' in k],
        'deepinfra': [k for k in all_key_names if 'DEEPINFRA_API_KEY' in k],
        'cloudflare': [k for k in all_key_names if 'CLOUDFLARE_API_KEY' in k],
        'mistral': [k for k in all_key_names if 'MISTRAL_API_KEY' in k],
    }

    for key_name in key_map['nvidia']:
        key = get(key_name)
        if not key:
            continue
        tag = key_name.split('_')[-1].lower() if key_name.count('_') > 3 else 'default'
        for model_id, base_name, bs in NVIDIA_MODELS:
            providers.append(NvidiaProvider(key, model_id, f'{base_name}-{tag}', batch_size=bs))

    for key_name in key_map['google']:
        key = get(key_name)
        if key:
            tag = key_name.split('_')[-1].lower() if key_name.count('_') > 3 else 'default'
            providers.append(GoogleProvider(key, f'google-{tag}'))

    for key_name in key_map['voyage']:
        key = get(key_name)
        if not key:
            continue
        tag = key_name.split('_')[-1].lower() if key_name.count('_') > 3 else 'default'
        for model in VOYAGE_MODELS:
            providers.append(VoyageProvider(key, model, f'{model}-{tag}'))

    for key_name in key_map['openrouter']:
        key = get(key_name)
        if not key:
            continue
        tag = key_name.split('_')[-1].lower() if key_name.count('_') > 3 else 'default'
        for model, base_name in OPENROUTER_MODELS:
            providers.append(OpenRouterProvider(key, model, f'{base_name}-{tag}'))

    for key_name in key_map['cohere']:
        key = get(key_name)
        if key:
            tag = key_name.split('_')[-1].lower() if key_name.count('_') > 3 else 'default'
            providers.append(CohereProvider(key, f'cohere-{tag}'))

    for key_name in key_map['deepinfra']:
        key = get(key_name)
        if key:
            tag = key_name.split('_')[-1].lower() if key_name.count('_') > 3 else 'default'
            providers.append(DeepInfraProvider(key, f'deepinfra-{tag}'))

    for key_name in key_map['cloudflare']:
        key = get(key_name)
        if key and cf_account_id:
            tag = key_name.split('_')[-1].lower() if key_name.count('_') > 3 else 'default'
            providers.append(CloudflareProvider(key, cf_account_id, f'cloudflare-{tag}'))

    for key_name in key_map['mistral']:
        key = get(key_name)
        if key:
            tag = key_name.split('_')[-1].lower() if key_name.count('_') > 3 else 'default'
            providers.append(MistralProvider(key, f'mistral-{tag}'))

    return [p for p in providers if p.is_available()]


def run_provider(provider, batch_url, store_url, pipeline_mode=False, check_url=None):
    try:
        if pipeline_mode:
            resp = http_post(batch_url, {'count': provider.batch_size,
                                          'worker_id': f'{HOSTNAME}-{provider.name}'})
        else:
            resp = http_post(batch_url, {'batch_size': provider.batch_size})
    except Exception as e:
        log.warning('API fetch error: %s', str(e)[:100])
        return 0

    chunks = resp.get('items', []) if pipeline_mode else resp.get('chunks', [])
    chunks = [c for c in chunks if (c.get('content') or c.get('content_preview', '')).strip()]
    if not chunks:
        return -1

    if check_url:
        try:
            check_resp = http_post(check_url, {'ids': [c['id'] for c in chunks]})
            already = set(str(i) for i in check_resp.get('embedded', []))
            if already:
                chunks = [c for c in chunks if str(c['id']) not in already]
                if not chunks:
                    return 0
        except Exception as e:
            log.warning('check-embedded failed, proceeding anyway: %s', str(e)[:100])

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
    parser = argparse.ArgumentParser(description='Fleet embedding consumer — ALL keys')
    parser.add_argument('--api', default='http://aio-01:5000')
    parser.add_argument('--target', default='chunks', choices=['chunks', 'code', 'pipeline'])
    args = parser.parse_args()

    check_url = f'{args.api}/knowledge/chunks/check-embedded'

    if args.target == 'pipeline':
        batch_url = f'{args.api}/pipeline/queues/embed/fetch'
        store_url = f'{args.api}/knowledge/chunks/store-embeddings'
    elif args.target == 'chunks':
        batch_url = f'{args.api}/knowledge/chunks/batch-embed'
        store_url = f'{args.api}/knowledge/chunks/store-embeddings'
    else:
        batch_url = f'{args.api}/documents/batch-embed'
        store_url = f'{args.api}/documents/store-embeddings'

    log.info('Worker %s starting — target=%s api=%s', HOSTNAME, args.target, args.api)
    log.info('Loading ALL embedding keys from %s...', args.api)

    providers = build_providers(args.api)

    from collections import Counter
    provider_types = Counter(p.name.rsplit('-', 1)[0] for p in providers)
    log.info('Active: %d providers across %d types: %s',
             len(providers), len(provider_types), dict(provider_types))

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

        count = run_provider(provider, batch_url, store_url,
                             pipeline_mode=(args.target == 'pipeline'),
                             check_url=check_url)
        if count == -1:
            empty_rounds += 1
            if empty_rounds >= 10:
                log.info('No work for 10 rounds, sleeping 30s')
                time.sleep(30)
                empty_rounds = 0
            else:
                time.sleep(3)
            continue

        empty_rounds = 0
        total += count

        if total > 0 and total % 200 < provider.batch_size:
            elapsed = time.time() - start_time
            rate = total / elapsed if elapsed > 0 else 0
            top = sorted(providers, key=lambda p: p.successes, reverse=True)[:10]
            summary = ', '.join(f'{p.name}:{p.successes}' for p in top if p.successes > 0)
            log.info('[%s] %d embedded (%.1f/sec) [%s]', HOSTNAME, total, rate, summary)

    elapsed = time.time() - start_time
    log.info('=== %s FINAL: %d embedded in %.0fs (%.1f/sec) ===', HOSTNAME, total, elapsed,
             total / elapsed if elapsed > 0 else 0)
    for p in sorted(providers, key=lambda p: p.successes, reverse=True):
        if p.successes > 0 or p.failures > 0:
            log.info('  %s: %d ok, %d fail', p.name, p.successes, p.failures)


if __name__ == '__main__':
    main()
