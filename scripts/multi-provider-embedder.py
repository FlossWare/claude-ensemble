#!/usr/bin/env python3
"""Multi-provider embedding backfill — Redis queue with independent provider consumers.

Each provider runs in its own thread, pulling chunks from a shared Redis queue
at its own pace. Slow providers (e.g., HF Spaces ~10s/call) never block fast
providers (NVIDIA ~1.5s/call).

Providers (all free tier, all 1024-dim native):
1. NVIDIA NIM (nv-embedqa-e5-v5, 1024-dim) — 40 RPM free
2. Cohere (embed-english-v3.0, 1024-dim) — trial tier
3. Jina AI (jina-embeddings-v3, 1024-dim) — 1M tokens/month free
4. Mistral (mistral-embed, 1024-dim) — 60 RPM free
5. Voyage AI (voyage-3, 1024-dim) — 5M tokens/month free
6. Google Gemini (gemini-embedding-001, 3072-dim truncated to 1024) — free tier
7. LightweightEmbeddings (bge-m3, 1024-dim) — free, no key, HF Spaces hosted
8. OpenRouter (llama-nemotron-embed-vl-1b-v2, 1024-dim) — free tier

Disabled: Local sentence-transformers (768-dim), Cloudflare bge-base (768-dim)

Architecture:
- Feeder thread: polls REST API for chunks needing embedding, pushes to Redis
- Provider threads: each independently pulls from Redis, embeds, stores results
- Main thread: logs stats, waits for shutdown

All DB access via REST API at localhost:5000, NEVER direct PostgreSQL.

Usage:
    python3 scripts/multi-provider-embedder.py --no-local --api http://localhost:5000
"""
import argparse
import json
import logging
import os
import signal
import sys
import time
import urllib.request
import urllib.error
from threading import Lock, Semaphore, Thread

import redis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('multi-embedder')

_shutdown = False
_feeder_done = False
_stats_lock = Lock()
_stats = {'total': 0, 'success': 0, 'failed': 0, 'by_provider': {}}

QUEUE_KEY = 'embedding:pending'
HIGH_WATER = 256
LOW_WATER = 64
TARGET_DIM = 1024
_api_semaphore = Semaphore(2)


def handle_signal(signum, frame):
    global _shutdown
    log.info('Shutdown requested')
    _shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def api_post(url, data, timeout=60):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method='POST',
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def api_get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read())


def normalize_dim(embedding, target=TARGET_DIM):
    if len(embedding) == target:
        return embedding
    if len(embedding) > target:
        return embedding[:target]
    return embedding + [0.0] * (target - len(embedding))


def http_post_json(url, data, headers=None, timeout=30):
    body = json.dumps(data).encode()
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, method='POST', headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class EmbeddingProvider:
    def __init__(self, name, batch_size=8):
        self.name = name
        self.batch_size = batch_size
        self.successes = 0
        self.failures = 0
        self.cooldown_until = 0

    def is_available(self):
        return time.time() >= self.cooldown_until

    def set_cooldown(self, seconds=60):
        self.cooldown_until = time.time() + seconds
        log.warning('%s: rate limited, cooling down %ds', self.name, seconds)

    def embed(self, texts):
        raise NotImplementedError


class LocalProvider(EmbeddingProvider):
    def __init__(self):
        super().__init__('local-mpnet', batch_size=64)
        self._model = None

    def _get_model(self):
        if self._model is None:
            log.info('Loading local sentence-transformers model...')
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-mpnet-base-v2')
            log.info('Local model loaded (768-dim)')
        return self._model

    def embed(self, texts):
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False, batch_size=64)
        return [e.tolist() for e in embeddings]


class JinaProvider(EmbeddingProvider):
    def __init__(self):
        super().__init__('jina', batch_size=16)
        self.api_key = os.getenv('PERSONAL_JINA_API_KEY', '')

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post_json(
            'https://api.jina.ai/v1/embeddings',
            {'input': texts, 'model': 'jina-embeddings-v3',
             'dimensions': TARGET_DIM},
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class GoogleProvider(EmbeddingProvider):
    def __init__(self):
        super().__init__('google', batch_size=8)
        self.api_key = os.getenv('PERSONAL_GOOGLE_API_KEY') or os.getenv('GOOGLE_API_KEY', '')

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        results = []
        for text in texts:
            data = http_post_json(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={self.api_key}',
                {'content': {'parts': [{'text': text[:2000]}]}},
                timeout=15,
            )
            emb = data.get('embedding', {}).get('values', [])
            results.append(normalize_dim(emb))
        return results


class CohereProvider(EmbeddingProvider):
    def __init__(self):
        super().__init__('cohere', batch_size=16)
        self.api_key = os.getenv('PERSONAL_COHERE_API_KEY', '')

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post_json(
            'https://api.cohere.com/v2/embed',
            {'texts': texts, 'model': 'embed-english-v3.0',
             'input_type': 'search_document', 'embedding_types': ['float']},
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        embeddings = data.get('embeddings', {}).get('float', [])
        return [normalize_dim(e) for e in embeddings]


class VoyageProvider(EmbeddingProvider):
    def __init__(self):
        super().__init__('voyage', batch_size=8)
        self.api_key = os.getenv('PERSONAL_VOYAGEAI_API_KEY', '')

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post_json(
            'https://api.voyageai.com/v1/embeddings',
            {'input': texts, 'model': 'voyage-3'},
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class MistralProvider(EmbeddingProvider):
    def __init__(self):
        super().__init__('mistral', batch_size=8)
        self.api_key = os.getenv('PERSONAL_MISTRAL_API_KEY', '')

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post_json(
            'https://api.mistral.ai/v1/embeddings',
            {'input': texts, 'model': 'mistral-embed'},
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class CloudflareProvider(EmbeddingProvider):
    """Disabled — bge-base-en-v1.5 outputs 768-dim only, can't do 1024."""
    def __init__(self):
        super().__init__('cloudflare', batch_size=8)

    def is_available(self):
        return False

    def embed(self, texts):
        return []


class LightweightEmbeddingsProvider(EmbeddingProvider):
    """Free hosted on HF Spaces — bge-m3, 1024-dim, 8K context, no key needed."""
    def __init__(self):
        super().__init__('lightweight', batch_size=4)
        self.url = 'https://lamhieu-lightweight-embeddings.hf.space/v1/embeddings'

    def is_available(self):
        return super().is_available()

    def embed(self, texts):
        data = http_post_json(
            self.url,
            {'input': texts, 'model': 'bge-m3', 'dimensions': TARGET_DIM},
            timeout=30,
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    """Free embedding via OpenRouter — llama-nemotron-embed-vl-1b-v2, 1024-dim."""
    def __init__(self):
        super().__init__('openrouter', batch_size=8)
        self.api_key = os.getenv('PERSONAL_OPENROUTER_API_KEY', '')

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post_json(
            'https://openrouter.ai/api/v1/embeddings',
            {'input': texts,
             'model': 'nvidia/llama-nemotron-embed-vl-1b-v2:free',
             'dimensions': TARGET_DIM},
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class OpenRouterNemotronProvider(EmbeddingProvider):
    """Free embedding via OpenRouter — nemotron-3-embed-1b, 2048-dim truncated to 1024."""
    def __init__(self):
        super().__init__('or-nemotron', batch_size=8)
        self.api_key = os.getenv('PERSONAL_OPENROUTER_API_KEY', '')

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        data = http_post_json(
            'https://openrouter.ai/api/v1/embeddings',
            {'input': texts,
             'model': 'nvidia/nemotron-3-embed-1b:free',
             'dimensions': 2048},
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class RemoteLocalProvider(EmbeddingProvider):
    """Local sentence-transformers model running on a remote machine (e.g. cabin-laptop-01).
    No API key needed, no rate limits — limited only by CPU speed."""
    def __init__(self, url, name='remote-local', batch_size=8):
        super().__init__(name, batch_size=batch_size)
        self.url = url

    def is_available(self):
        if not super().is_available():
            return False
        try:
            req = urllib.request.Request(f'{self.url}/health')
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                return data.get('model_loaded', False)
        except Exception:
            return False

    def embed(self, texts):
        data = http_post_json(
            f'{self.url}/embeddings',
            {'texts': texts},
            timeout=60,
        )
        return [normalize_dim(e) for e in data['embeddings']]


class NvidiaProvider(EmbeddingProvider):
    def __init__(self):
        super().__init__('nvidia', batch_size=8)
        self.api_key = os.getenv('NVIDIA_API_KEY', '')

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        cleaned = [t[:400] if t.strip() else 'empty' for t in texts]
        data = http_post_json(
            'https://integrate.api.nvidia.com/v1/embeddings',
            {'model': 'nvidia/nv-embedqa-e5-v5',
             'input': cleaned, 'input_type': 'passage',
             'encoding_format': 'float', 'truncate': 'END'},
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


class NvidiaModelProvider(EmbeddingProvider):
    """Generic NVIDIA NIM embedding provider — works with any NVIDIA model."""
    def __init__(self, model_id, name, batch_size=8):
        super().__init__(name, batch_size=batch_size)
        self.api_key = os.getenv('NVIDIA_API_KEY', '')
        self.model_id = model_id

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def embed(self, texts):
        cleaned = [t[:400] if t.strip() else 'empty' for t in texts]
        data = http_post_json(
            'https://integrate.api.nvidia.com/v1/embeddings',
            {'model': self.model_id,
             'input': cleaned, 'input_type': 'passage',
             'encoding_format': 'float', 'truncate': 'END'},
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        return [normalize_dim(item['embedding']) for item in data['data']]


def update_stats(provider_name, count, success=True):
    with _stats_lock:
        _stats['total'] += count
        if success:
            _stats['success'] += count
        else:
            _stats['failed'] += count
        if provider_name not in _stats['by_provider']:
            _stats['by_provider'][provider_name] = {'success': 0, 'failed': 0}
        key = 'success' if success else 'failed'
        _stats['by_provider'][provider_name][key] += count


def feeder_loop(r, batch_url):
    """Polls REST API for chunks needing embedding and pushes to Redis queue."""
    global _feeder_done
    enqueued_ids = set()
    empty_rounds = 0

    log.info('Feeder: starting (%s)', batch_url)
    while not _shutdown:
        queue_len = r.llen(QUEUE_KEY)
        if queue_len >= HIGH_WATER:
            time.sleep(2)
            continue

        try:
            resp = api_post(batch_url, {
                'batch_size': min(HIGH_WATER - queue_len, 256)
            })
        except Exception as e:
            log.warning('Feeder: API error: %s', str(e)[:100])
            time.sleep(5)
            continue

        chunks = resp.get('chunks', [])
        chunks = [c for c in chunks if c['id'] not in enqueued_ids
                  and (c.get('content') or c.get('content_preview', '')).strip()]

        if not chunks:
            empty_rounds += 1
            if empty_rounds >= 3:
                log.info('Feeder: no more chunks to embed')
                break
            time.sleep(5)
            continue

        empty_rounds = 0
        pipe = r.pipeline()
        for c in chunks:
            task = json.dumps({
                'id': c['id'],
                'content': c.get('content') or c.get('content_preview') or '',
                'file_path': c.get('file_path', ''),
            })
            pipe.rpush(QUEUE_KEY, task)
            enqueued_ids.add(c['id'])
        pipe.execute()
        log.info('Feeder: enqueued %d chunks (queue: %d)', len(chunks), r.llen(QUEUE_KEY))

    _feeder_done = True
    log.info('Feeder: done (enqueued %d total)', len(enqueued_ids))


def provider_loop(provider, r, store_url):
    """Independent consumer loop — pulls from Redis, embeds, stores results."""
    log.info('%s: consumer started (batch_size=%d)', provider.name, provider.batch_size)

    while not _shutdown:
        if not provider.is_available():
            wait = provider.cooldown_until - time.time()
            if wait > 0:
                time.sleep(min(wait, 5))
            continue

        batch = []
        for _ in range(provider.batch_size):
            item = r.lpop(QUEUE_KEY)
            if item is None:
                break
            batch.append(json.loads(item))

        if not batch:
            if not _feeder_done:
                time.sleep(1)
                continue
            if r.llen(QUEUE_KEY) == 0:
                log.info('%s: queue empty and feeder done, exiting', provider.name)
                break
            time.sleep(1)
            continue

        ids = [c['id'] for c in batch]
        texts = [c.get('content', '') or 'empty' for c in batch]
        texts = [t if t.strip() else 'empty' for t in texts]

        try:
            embeddings = provider.embed(texts)

            with _api_semaphore:
                store_resp = api_post(store_url, {
                    'embeddings': [
                        {'id': id_, 'embedding': emb}
                        for id_, emb in zip(ids, embeddings)
                    ]
                }, timeout=120)

            stored = store_resp.get('updated', 0)
            provider.successes += stored
            update_stats(provider.name, stored, success=True)

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
            update_stats(provider.name, len(batch), success=False)
            log.warning('%s: HTTP %d on batch of %d%s', provider.name, e.code, len(batch),
                        f' — {body}' if body else '')
        except Exception as e:
            provider.failures += 1
            if provider.failures >= 5:
                provider.set_cooldown(300)
            update_stats(provider.name, len(batch), success=False)
            log.warning('%s: %s', provider.name, str(e)[:120])

    log.info('%s: consumer stopped (%d success, %d fail)',
             provider.name, provider.successes, provider.failures)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', default='http://localhost:5000')
    parser.add_argument('--redis-host', default='localhost')
    parser.add_argument('--redis-port', type=int, default=6379)
    parser.add_argument('--no-local', action='store_true',
                        help='Skip local sentence-transformers (saves CPU)')
    parser.add_argument('--target', default='chunks',
                        choices=['chunks', 'code'],
                        help='Which table to embed: chunks=knowledge.chunks, code=knowledge.code_embeddings')
    parser.add_argument('--consumer-only', action='store_true',
                        help='Consumer mode: pull from Redis queue only, no feeder thread')
    parser.add_argument('--fetch-keys', action='store_true',
                        help='Fetch API keys from orchestrator REST API before starting')
    parser.add_argument('--remote-embed', default='',
                        help='URL of a remote embedding service (e.g. http://cabin-laptop-01:8103)')
    args = parser.parse_args()

    if args.target == 'chunks':
        args.batch_url = f'{args.api}/knowledge/chunks/batch-embed'
        args.store_url = f'{args.api}/knowledge/chunks/store-embeddings'
    else:
        args.batch_url = f'{args.api}/documents/batch-embed'
        args.store_url = f'{args.api}/documents/store-embeddings'

    if args.fetch_keys:
        key_names = [
            'NVIDIA_API_KEY', 'PERSONAL_MISTRAL_API_KEY', 'PERSONAL_OPENROUTER_API_KEY',
            'PERSONAL_VOYAGEAI_API_KEY', 'PERSONAL_GOOGLE_API_KEY',
            'PERSONAL_COHERE_API_KEY', 'PERSONAL_JINA_API_KEY',
        ]
        for kn in key_names:
            if not os.environ.get(kn):
                try:
                    resp = api_get(f'{args.api}/secrets/{kn}')
                    val = resp.get('value', '')
                    if val:
                        os.environ[kn] = val
                        log.info('Fetched key: %s', kn)
                except Exception:
                    pass

    r = redis.Redis(host=args.redis_host, port=args.redis_port,
                    decode_responses=True)
    try:
        r.ping()
        log.info('Redis connected: %s:%d', args.redis_host, args.redis_port)
    except redis.ConnectionError:
        log.error('Cannot connect to Redis at %s:%d', args.redis_host, args.redis_port)
        sys.exit(1)

    providers = []
    if not args.no_local:
        providers.append(LocalProvider())
    if args.remote_embed:
        for i, url in enumerate(args.remote_embed.split(',')):
            url = url.strip()
            if url:
                name = f'cabin-local-{i}' if i > 0 else 'cabin-local'
                providers.append(RemoteLocalProvider(url, name=name, batch_size=8))
    providers.extend([
        GoogleProvider(),
        CohereProvider(),
        VoyageProvider(),
        CloudflareProvider(),
        NvidiaProvider(),
        NvidiaModelProvider('nvidia/nv-embed-v1', 'nvidia-v1'),
        NvidiaModelProvider('nvidia/nv-embedcode-7b-v1', 'nvidia-code', batch_size=4),
        NvidiaModelProvider('nvidia/llama-nemotron-embed-1b-v2', 'nvidia-nemotron-v2'),
        NvidiaModelProvider('nvidia/llama-nemotron-embed-vl-1b-v2', 'nvidia-nemotron-vl'),
        NvidiaModelProvider('nvidia/nemotron-3-embed-1b', 'nvidia-nemotron-3'),
        JinaProvider(),
        MistralProvider(),
        LightweightEmbeddingsProvider(),
        OpenRouterEmbeddingProvider(),
        OpenRouterNemotronProvider(),
    ])

    available = [p for p in providers if p.is_available()]
    log.info('Available providers: %s', ', '.join(p.name for p in available))
    if not available:
        log.error('No embedding providers available!')
        sys.exit(1)

    try:
        stats = api_get(f'{args.api}/documents/stats')
        log.info('DB: %d chunks, %d files', stats['total_chunks'], stats['unique_files'])
    except Exception as e:
        log.warning('Could not fetch DB stats: %s', str(e)[:100])

    start_time = time.time()

    mode = 'consumer-only' if args.consumer_only else 'feeder+consumer'
    log.info('Target: %s (%s) mode=%s', args.target, args.batch_url, mode)

    feeder = None
    if not args.consumer_only:
        feeder = Thread(target=feeder_loop, args=(r, args.batch_url), daemon=True, name='feeder')
        feeder.start()

    consumers = []
    for provider in available:
        t = Thread(target=provider_loop, args=(provider, r, args.store_url),
                   daemon=True, name=f'consumer-{provider.name}')
        t.start()
        consumers.append(t)

    global _shutdown
    try:
        while not _shutdown:
            time.sleep(10)
            elapsed = time.time() - start_time
            rate = _stats['success'] / elapsed if elapsed > 0 else 0
            provider_summary = ', '.join(
                f'{k}:{v["success"]}' for k, v in sorted(_stats['by_provider'].items())
                if v['success'] > 0
            )
            queue_len = r.llen(QUEUE_KEY)
            log.info('Stats: %d embedded (%.1f/sec) queue=%d [%s]',
                     _stats['success'], rate, queue_len, provider_summary)

            if args.consumer_only:
                if queue_len == 0:
                    all_done = all(not t.is_alive() for t in consumers)
                    if all_done:
                        break
            else:
                if _feeder_done and queue_len == 0:
                    all_done = all(not t.is_alive() for t in consumers)
                    if all_done:
                        break
    except KeyboardInterrupt:
        _shutdown = True

    if feeder:
        feeder.join(timeout=5)
    for t in consumers:
        t.join(timeout=10)

    elapsed = time.time() - start_time
    log.info('=== FINAL STATS ===')
    log.info('Total: %d success, %d failed in %.1fs (%.1f/sec)',
             _stats['success'], _stats['failed'], elapsed,
             _stats['success'] / elapsed if elapsed > 0 else 0)
    for name, s in sorted(_stats['by_provider'].items()):
        log.info('  %s: %d success, %d failed', name, s['success'], s['failed'])


if __name__ == '__main__':
    main()
