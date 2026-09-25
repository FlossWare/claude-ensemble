#!/usr/bin/env python3
"""Backfill content for document stubs via REST API.

Fetches document stubs (metadata-only records) from the REST API, downloads
their actual content from source URLs, and stores it back via REST API.

Handles: arxiv (abstracts→full text), internet-archive, project-gutenberg,
web-scrape, postgresql-docs, cpython-source, linux-kernel-docs, etc.

Usage:
    python3 scripts/backfill-content.py [--batch 50] [--source arxiv-ai] [--api http://localhost:5000]
"""
import argparse
import json
import logging
import signal
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('backfill-content')

_shutdown = False

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
    req = urllib.request.Request(url, method='GET')
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_url(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (research-bot; +https://github.com/sfloess)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        log.debug('Failed to fetch %s: %s', url, e)
        return None


def extract_arxiv_content(metadata):
    """Extract content from arxiv metadata - use abstract + try to get full text."""
    arxiv_id = metadata.get('arxiv_id', '')
    abstract = metadata.get('abstract', '')
    title = metadata.get('title', '')

    content_parts = []
    if title:
        content_parts.append(f"# {title}\n")
    if abstract:
        content_parts.append(f"## Abstract\n\n{abstract}\n")

    if arxiv_id:
        clean_id = arxiv_id.replace('v1', '').replace('v2', '').replace('v3', '')
        txt_url = f"https://arxiv.org/abs/{clean_id}"
        html = fetch_url(txt_url, timeout=15)
        if html and len(html) > len(abstract) * 2:
            import re
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 500:
                content_parts.append(f"## Full Text\n\n{text[:50000]}\n")

    return '\n'.join(content_parts) if content_parts else None


def extract_gutenberg_content(metadata):
    """Try to fetch Project Gutenberg text."""
    gut_id = metadata.get('id', metadata.get('gutenberg_id', ''))
    if not gut_id:
        return None
    url = f"https://www.gutenberg.org/files/{gut_id}/{gut_id}-0.txt"
    content = fetch_url(url, timeout=30)
    if not content:
        url = f"https://www.gutenberg.org/cache/epub/{gut_id}/pg{gut_id}.txt"
        content = fetch_url(url, timeout=30)
    return content[:100000] if content else None


def extract_generic_content(doc):
    """For documents with a URL in metadata, try to fetch it."""
    metadata = doc.get('metadata', {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}

    url = metadata.get('url') or metadata.get('source_url') or metadata.get('link', '')
    if url and url.startswith('http'):
        return fetch_url(url, timeout=30)

    title = metadata.get('title', doc.get('file_name', ''))
    abstract = metadata.get('abstract', metadata.get('description', ''))
    if title or abstract:
        parts = []
        if title:
            parts.append(f"# {title}")
        if abstract:
            parts.append(abstract)
        combined = '\n\n'.join(parts)
        if len(combined) > 50:
            return combined
    return None


SOURCE_HANDLERS = {
    'arxiv-ai': extract_arxiv_content,
    'arxiv-cv': extract_arxiv_content,
    'arxiv-cl': extract_arxiv_content,
    'arxiv-ml': extract_arxiv_content,
    'arxiv-robotics': extract_arxiv_content,
    'arxiv-neural': extract_arxiv_content,
    'arxiv-data': extract_arxiv_content,
    'arxiv-theory': extract_arxiv_content,
    'project-gutenberg': extract_gutenberg_content,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int, default=50)
    parser.add_argument('--source', default=None, help='Filter by source (e.g. arxiv-ai)')
    parser.add_argument('--api', default='http://localhost:5000')
    parser.add_argument('--max-docs', type=int, default=0, help='Max docs to process (0=unlimited)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    stats = api_get(f'{args.api}/documents/stats')
    log.info('DB stats: %s', json.dumps(stats))

    total_processed = 0
    total_filled = 0
    total_skipped = 0
    start_time = time.time()

    while not _shutdown:
        try:
            params = {'batch_size': args.batch}
            if args.source:
                params['source'] = args.source

            resp = api_post(f'{args.api}/documents/fetch-stubs', params)
            stubs = resp.get('stubs', [])
            if not stubs:
                log.info('No more stubs to process. Done!')
                break

            for doc in stubs:
                if _shutdown:
                    break

                doc_id = doc['id']
                source = doc.get('source', '')
                metadata = doc.get('metadata', {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}

                handler = SOURCE_HANDLERS.get(source, lambda m: extract_generic_content(doc))
                content = handler(metadata)

                if content and len(content.strip()) > 50:
                    if not args.dry_run:
                        api_post(f'{args.api}/documents/update-content', {
                            'id': doc_id,
                            'content': content[:100000],
                        })
                    total_filled += 1
                else:
                    total_skipped += 1

                total_processed += 1

            elapsed = time.time() - start_time
            rate = total_processed / elapsed if elapsed > 0 else 0
            log.info('Processed %d docs (filled: %d, skipped: %d, %.1f/sec)',
                     total_processed, total_filled, total_skipped, rate)

            if args.max_docs and total_processed >= args.max_docs:
                log.info('Reached max docs (%d)', args.max_docs)
                break

        except urllib.error.HTTPError as e:
            if e.code == 404:
                log.warning('Endpoint not found (404) - need to deploy fetch-stubs/update-content endpoints')
                break
            log.error('HTTP error %d: %s', e.code, e.read().decode()[:200])
            time.sleep(5)
        except Exception as e:
            log.error('Error: %s', e)
            time.sleep(5)

    elapsed = time.time() - start_time
    log.info('Finished: processed %d, filled %d, skipped %d in %.1fs',
             total_processed, total_filled, total_skipped, elapsed)


if __name__ == '__main__':
    main()
