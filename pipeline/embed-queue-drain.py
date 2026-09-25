#!/usr/bin/env python3
"""Embed queue drain — completes embed queue items and chains to graph queue.

The actual embedding is handled by fleet-embed-consumer workers polling
/knowledge/chunks/batch-embed directly. This worker drains the Redis embed
queue to keep the pipeline flowing and chains items to the graph queue for
OrientDB ingestion.

Usage:
    python3 embed-queue-drain.py --api http://192.168.2.5:5000
"""
import argparse
import json
import logging
import signal
import socket
import sys
import time
import urllib.request
import urllib.error

HOSTNAME = socket.gethostname()
_shutdown = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('embed-drain')


def handle_signal(signum, frame):
    global _shutdown
    log.info('Shutdown requested')
    _shutdown = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def http_post(url, data, timeout=30):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method='POST',
                                headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser(description='Embed queue drain worker')
    parser.add_argument('--api', default='http://localhost:5000')
    parser.add_argument('--batch', type=int, default=20)
    parser.add_argument('--worker-id', default=f'{HOSTNAME}-embed-drain')
    args = parser.parse_args()

    api = args.api
    worker_id = args.worker_id

    log.info('Worker %s starting — api=%s', worker_id, api)

    start_time = time.time()
    total = 0
    errors = 0
    empty_rounds = 0

    while not _shutdown:
        try:
            resp = http_post(f'{api}/queue/fetch/embed',
                             {'limit': args.batch, 'worker_id': worker_id})
        except urllib.error.HTTPError as e:
            if e.code == 204:
                empty_rounds += 1
                if empty_rounds >= 10:
                    time.sleep(10)
                    empty_rounds = 0
                else:
                    time.sleep(3)
                continue
            log.warning('Queue fetch error: HTTP %d', e.code)
            time.sleep(5)
            continue
        except Exception as e:
            log.warning('Queue fetch error: %s', str(e)[:100])
            time.sleep(5)
            continue

        items = resp.get('items', [])
        if not items:
            empty_rounds += 1
            if empty_rounds >= 10:
                time.sleep(10)
                empty_rounds = 0
            else:
                time.sleep(3)
            continue

        empty_rounds = 0

        for item in items:
            item_id = item.get('id', '')
            try:
                http_post(f'{api}/queue/complete', {
                    'item_id': item_id,
                    'worker_id': worker_id,
                    'chain': True,
                })
                total += 1
            except Exception as e:
                errors += 1
                log.warning('Complete error for %s: %s', item_id, str(e)[:100])
                try:
                    http_post(f'{api}/queue/fail', {
                        'item_id': item_id,
                        'worker_id': worker_id,
                        'error': str(e)[:200],
                    })
                except Exception:
                    pass

        if total > 0 and total % 100 < args.batch:
            elapsed = time.time() - start_time
            rate = total / elapsed if elapsed > 0 else 0
            log.info('[%s] drained=%d errors=%d (%.1f/sec)',
                     worker_id, total, errors, rate)

    elapsed = time.time() - start_time
    log.info('=== %s FINAL: %d drained, %d errors in %.0fs ===',
             worker_id, total, errors, elapsed)


if __name__ == '__main__':
    main()
