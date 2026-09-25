#!/usr/bin/env python3
"""Fleet chunking consumer — REST API only, zero dependencies beyond stdlib.

Designed to run on fleet workers with no pip installs. Each worker:
1. Fetches unchunked documents from orchestrator REST API
2. Calls external chunking APIs (Jina, chunk.fit) to split them
3. Falls back to local recursive text splitting if APIs unavailable
4. Stores resulting chunks back via REST API

Usage:
    python3 fleet-chunk-consumer.py --api http://aio-01:5000
    python3 fleet-chunk-consumer.py --api http://localhost:5000  # via SSH tunnel
"""
import argparse
import hashlib
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
import re

_nossl = ssl.create_default_context()
_nossl.check_hostname = False
_nossl.verify_mode = ssl.CERT_NONE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('fleet-chunker')

_shutdown = False
HOSTNAME = socket.gethostname()
DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP = 50


def handle_signal(signum, frame):
    global _shutdown
    log.info('Shutdown requested')
    _shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def http_post(url, data, headers=None, timeout=30):
    body = json.dumps(data).encode()
    hdrs = {'Content-Type': 'application/json', 'User-Agent': 'fleet-chunker/1.0'}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, method='POST', headers=hdrs)
    ctx = _nossl if 'aio-01' not in url and 'localhost' not in url else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read())


def http_get(url, timeout=15):
    ctx = _nossl if 'aio-01' not in url and 'localhost' not in url else None
    req = urllib.request.Request(url, headers={'User-Agent': 'fleet-chunker/1.0'})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read())


def fetch_key(api_base, key_name):
    try:
        resp = http_get(f'{api_base}/secrets/{key_name}')
        return resp.get('value', '')
    except Exception:
        return ''


def content_hash(text):
    return hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()[:16]


def approx_tokens(text):
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Chunking providers
# ---------------------------------------------------------------------------

class ChunkProvider:
    def __init__(self, name):
        self.name = name
        self.successes = 0
        self.failures = 0
        self.cooldown_until = 0
        self.consecutive_errors = 0

    def is_available(self):
        return time.time() >= self.cooldown_until

    def set_cooldown(self, seconds=60):
        self.cooldown_until = time.time() + seconds

    def chunk(self, text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
        raise NotImplementedError


class JinaSegmenterProvider(ChunkProvider):
    """Jina AI Segmenter — free, no API key needed (20 RPM without key)."""
    def __init__(self, api_key=''):
        super().__init__('jina-segmenter')
        self.api_key = api_key

    def chunk(self, text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
        hdrs = {'Accept': 'application/json'}
        if self.api_key:
            hdrs['Authorization'] = f'Bearer {self.api_key}'
        data = http_post(
            'https://api.jina.ai/v1/segment',
            {
                'content': text[:64000],
                'return_chunks': True,
                'max_chunk_length': chunk_size,
            },
            headers=hdrs,
            timeout=30,
        )
        chunks = data.get('chunks', [])
        if not chunks:
            raise ValueError('Jina returned no chunks')
        return [c if isinstance(c, str) else c.get('text', str(c)) for c in chunks]


class UnstructuredProvider(ChunkProvider):
    """Unstructured Transform — jobs-based API at platform-api.transform.unstructured.io.
    Free tier, needs API key from transform.unstructured.io."""
    BASE = 'https://platform-api.transform.unstructured.io/api/v1'

    def __init__(self, api_key):
        super().__init__('unstructured')
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def _api_get(self, path):
        req = urllib.request.Request(
            f'{self.BASE}{path}',
            headers={
                'Accept': 'application/json',
                'User-Agent': 'fleet-chunker/1.0',
                'unstructured-api-key': self.api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=30, context=_nossl) as resp:
            return json.loads(resp.read())

    def chunk(self, text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
        boundary = f'----boundary{int(time.time()*1000)}'
        body_parts = []

        def add_field(name, value):
            body_parts.append(f'--{boundary}\r\n')
            body_parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n')
            body_parts.append(f'{value}\r\n')

        body_parts.append(f'--{boundary}\r\n')
        body_parts.append('Content-Disposition: form-data; name="input_files"; filename="doc.txt"\r\n')
        body_parts.append('Content-Type: text/plain\r\n\r\n')
        body_parts.append(text + '\r\n')

        job_nodes = json.dumps({'job_nodes': [
            {'name': 'Partitioner', 'type': 'partition', 'subtype': 'vlm',
             'settings': {'is_dynamic': True, 'allow_fast': True}},
            {'name': 'Chunker', 'type': 'chunk', 'subtype': 'chunk_by_title',
             'settings': {'max_characters': chunk_size,
                          'combine_text_under_n_chars': chunk_size // 2}},
        ]})
        add_field('request_data', job_nodes)
        body_parts.append(f'--{boundary}--\r\n')

        body_bytes = ''.join(body_parts).encode('utf-8')
        req = urllib.request.Request(
            f'{self.BASE}/jobs/',
            data=body_bytes,
            method='POST',
            headers={
                'Accept': 'application/json',
                'User-Agent': 'fleet-chunker/1.0',
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'unstructured-api-key': self.api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=30, context=_nossl) as resp:
            job = json.loads(resp.read())

        job_id = job['id']
        chunk_node = None
        for node in job.get('output_node_files', []):
            if node.get('node_type') == 'chunk':
                chunk_node = node
                break
        if not chunk_node:
            chunk_node = job.get('output_node_files', [{}])[-1]

        for _ in range(30):
            time.sleep(2)
            status = self._api_get(f'/jobs/{job_id}')
            if status.get('status') == 'COMPLETED':
                break
            if status.get('status') == 'FAILED':
                raise ValueError(f'Unstructured job {job_id} failed')
        else:
            raise ValueError(f'Unstructured job {job_id} timed out')

        file_id = chunk_node.get('file_id', '')
        node_id = chunk_node.get('node_id', '')
        elements = self._api_get(f'/jobs/{job_id}/download?file_id={file_id}&node_id={node_id}')

        chunks = []
        for el in elements:
            text_val = el.get('text', '')
            if text_val and text_val.strip():
                chunks.append(text_val.strip())
        if not chunks:
            raise ValueError('Unstructured returned no elements')
        return chunks


class ChunkFitRecursiveProvider(ChunkProvider):
    """chunk.fit — 1,000 free requests/month, recursive splitter via LangChain."""
    def __init__(self, api_key):
        super().__init__('chunkfit-recursive')
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def chunk(self, text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
        data = http_post(
            'https://chunk.fit/api/v1/langchain/splitters/recursive',
            {
                'text': text,
                'chunk_size': chunk_size,
                'chunk_overlap': overlap,
            },
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        chunks = data.get('chunks', data.get('result', []))
        if not chunks:
            raise ValueError('chunk.fit returned no chunks')
        return [c if isinstance(c, str) else c.get('text', str(c)) for c in chunks]


class ChunkFitMarkdownProvider(ChunkProvider):
    """chunk.fit — markdown-aware splitter (splits at headers, lists, code blocks)."""
    def __init__(self, api_key):
        super().__init__('chunkfit-markdown')
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def chunk(self, text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
        data = http_post(
            'https://chunk.fit/api/v1/langchain/splitters/markdown',
            {
                'text': text,
                'chunk_size': chunk_size,
                'chunk_overlap': overlap,
            },
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        chunks = data.get('chunks', data.get('result', []))
        if not chunks:
            raise ValueError('chunk.fit markdown returned no chunks')
        return [c if isinstance(c, str) else c.get('text', str(c)) for c in chunks]


class ChunkFitTokenProvider(ChunkProvider):
    """chunk.fit — token-based splitter."""
    def __init__(self, api_key):
        super().__init__('chunkfit-token')
        self.api_key = api_key

    def is_available(self):
        return bool(self.api_key) and super().is_available()

    def chunk(self, text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
        data = http_post(
            'https://chunk.fit/api/v1/langchain/splitters/token',
            {
                'text': text,
                'chunk_size': chunk_size,
                'chunk_overlap': overlap,
            },
            headers={'Authorization': f'Bearer {self.api_key}'},
            timeout=30,
        )
        chunks = data.get('chunks', data.get('result', []))
        if not chunks:
            raise ValueError('chunk.fit token returned no chunks')
        return [c if isinstance(c, str) else c.get('text', str(c)) for c in chunks]


class RecursiveLocalProvider(ChunkProvider):
    """Local recursive text splitting — no API calls, always available."""
    SEPARATORS = ['\n\n', '\n', '. ', '? ', '! ', '; ', ', ', ' ', '']

    def __init__(self):
        super().__init__('local-recursive')

    def is_available(self):
        return True

    def chunk(self, text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
        return self._split(text, self.SEPARATORS, chunk_size, overlap)

    def _split(self, text, separators, chunk_size, overlap):
        if not text.strip():
            return []
        if len(text) <= chunk_size:
            return [text]

        sep = separators[0] if separators else ''
        rest = separators[1:] if len(separators) > 1 else ['']

        if sep == '':
            chunks = []
            for i in range(0, len(text), chunk_size - overlap):
                piece = text[i:i + chunk_size]
                if piece.strip():
                    chunks.append(piece)
            return chunks

        parts = text.split(sep)
        chunks = []
        current = ''

        for part in parts:
            candidate = (current + sep + part) if current else part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current.strip():
                    if len(current) <= chunk_size:
                        chunks.append(current)
                    else:
                        chunks.extend(self._split(current, rest, chunk_size, overlap))
                current = part

        if current.strip():
            if len(current) <= chunk_size:
                chunks.append(current)
            else:
                chunks.extend(self._split(current, rest, chunk_size, overlap))

        return chunks


class SentenceLocalProvider(ChunkProvider):
    """Local sentence-based splitting — splits at sentence boundaries, merges to fit size."""
    SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

    def __init__(self):
        super().__init__('local-sentence')

    def is_available(self):
        return True

    def chunk(self, text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
        sentences = self.SENTENCE_RE.split(text)
        if not sentences:
            return [text] if text.strip() else []

        chunks = []
        current = ''
        for sent in sentences:
            if not sent.strip():
                continue
            candidate = (current + ' ' + sent) if current else sent
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current.strip():
                    chunks.append(current.strip())
                if len(sent) > chunk_size:
                    for i in range(0, len(sent), chunk_size - overlap):
                        piece = sent[i:i + chunk_size]
                        if piece.strip():
                            chunks.append(piece.strip())
                    current = ''
                else:
                    current = sent
        if current.strip():
            chunks.append(current.strip())
        return chunks


# ---------------------------------------------------------------------------
# Main consumer loop
# ---------------------------------------------------------------------------

def process_document(provider, doc, store_url):
    """Chunk one document and store results. Returns chunk count or 0 on error."""
    doc_id = doc['id']
    text = doc.get('content', '')
    if not text or not text.strip():
        return 0

    try:
        raw_chunks = provider.chunk(text)
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        if e.code == 429:
            provider.set_cooldown(120)
        elif e.code == 402:
            provider.set_cooldown(3600)
            log.warning('%s: quota exhausted (402), cooldown 1h', provider.name)
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

    if not raw_chunks:
        return 0

    chunks_payload = []
    for i, chunk_text in enumerate(raw_chunks):
        if not chunk_text or not chunk_text.strip():
            continue
        chunks_payload.append({
            'content': chunk_text.strip(),
            'index': i,
            'token_count': approx_tokens(chunk_text),
            'content_hash': content_hash(chunk_text),
        })

    if not chunks_payload:
        return 0

    try:
        resp = http_post(store_url, {
            'document_id': doc_id,
            'chunks': chunks_payload,
        }, timeout=60)
        stored = resp.get('stored_chunks', 0)
        provider.successes += 1
        provider.consecutive_errors = 0
        return stored
    except Exception as e:
        log.warning('Store error doc %s: %s', doc_id, str(e)[:120])
        return 0


def main():
    parser = argparse.ArgumentParser(description='Fleet chunking consumer')
    parser.add_argument('--api', default='http://aio-01:5000')
    parser.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument('--overlap', type=int, default=DEFAULT_OVERLAP)
    parser.add_argument('--batch', type=int, default=5,
                        help='Documents to fetch per round')
    args = parser.parse_args()

    pending_url = f'{args.api}/knowledge/chunks/pending?limit={args.batch}'
    store_url = f'{args.api}/knowledge/chunks/store'

    log.info('Worker %s starting — api=%s chunk_size=%d overlap=%d',
             HOSTNAME, args.api, args.chunk_size, args.overlap)

    # Fetch optional API keys (Jina free=20RPM, with key=200RPM)
    jina_key = fetch_key(args.api, 'JINA_API_KEY')
    chunkfit_key = fetch_key(args.api, 'CHUNKFIT_API_KEY')
    unstructured_key = fetch_key(args.api, 'UNSTRUCTURED_API_KEY')

    providers = [p for p in [
        JinaSegmenterProvider(jina_key),
        UnstructuredProvider(unstructured_key),
        ChunkFitRecursiveProvider(chunkfit_key),
        ChunkFitMarkdownProvider(chunkfit_key),
        ChunkFitTokenProvider(chunkfit_key),
        SentenceLocalProvider(),
        RecursiveLocalProvider(),
    ] if p.is_available()]

    log.info('Active providers (%d): %s', len(providers),
             ', '.join(p.name for p in providers))

    start_time = time.time()
    total_docs = 0
    total_chunks = 0
    empty_rounds = 0
    provider_idx = 0

    while not _shutdown:
        # Fetch unchunked documents
        try:
            resp = http_get(pending_url, timeout=15)
        except Exception as e:
            log.warning('API fetch error: %s', str(e)[:100])
            time.sleep(10)
            continue

        docs = resp.get('items', [])
        if not docs:
            empty_rounds += 1
            if empty_rounds >= 10:
                log.info('No unchunked docs for 10 rounds, sleeping 60s')
                time.sleep(60)
                empty_rounds = 0
            else:
                time.sleep(5)
            continue

        empty_rounds = 0

        for doc in docs:
            if _shutdown:
                break

            # Pick next available provider (round-robin)
            available = [p for p in providers if p.is_available()]
            if not available:
                time.sleep(5)
                continue

            provider = available[provider_idx % len(available)]
            provider_idx += 1

            stored = process_document(provider, doc, store_url)
            if stored > 0:
                total_docs += 1
                total_chunks += stored

        # Periodic stats
        if total_docs > 0 and total_docs % 10 == 0:
            elapsed = time.time() - start_time
            rate = total_docs / elapsed if elapsed > 0 else 0
            summary = ', '.join(
                f'{p.name}:{p.successes}ok/{p.failures}err'
                for p in providers if p.successes > 0 or p.failures > 0
            )
            log.info('[%s] %d docs → %d chunks (%.1f docs/sec) [%s]',
                     HOSTNAME, total_docs, total_chunks, rate, summary)

    elapsed = time.time() - start_time
    log.info('=== %s FINAL: %d docs → %d chunks in %.0fs ===',
             HOSTNAME, total_docs, total_chunks, elapsed)
    for p in providers:
        if p.successes > 0 or p.failures > 0:
            log.info('  %s: %d ok, %d fail', p.name, p.successes, p.failures)


if __name__ == '__main__':
    main()
