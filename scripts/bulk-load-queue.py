#!/usr/bin/env python3
"""Bulk-load chunks to Redis queue with cursor pagination. Continues from min_id."""
import json, sys, time, urllib.request, urllib.error
import redis

API = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:5000'
REDIS_HOST = sys.argv[2] if len(sys.argv) > 2 else 'localhost'
MIN_ID = int(sys.argv[3]) if len(sys.argv) > 3 else 2659073
BATCH = 500
QUEUE_KEY = 'embedding:pending'

r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
total = 0
min_id = MIN_ID
retries = 0

print(f'Bulk-loading from min_id={min_id}, api={API}, redis={REDIS_HOST}')

while True:
    try:
        body = json.dumps({'batch_size': BATCH, 'min_id': min_id, 'skip_embed_check': True}).encode()
        req = urllib.request.Request(f'{API}/knowledge/chunks/batch-embed',
                                     data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        retries = 0
    except Exception as e:
        retries += 1
        print(f'API error at min_id={min_id}: {e}')
        if retries > 10:
            print('Too many retries, exiting')
            break
        time.sleep(min(retries * 5, 60))
        continue

    chunks = data.get('chunks', [])
    if not chunks:
        print(f'No more chunks. Total loaded: {total:,}')
        break

    pipe = r.pipeline()
    for c in chunks:
        task = json.dumps({'id': c['id'], 'content': c.get('content', '') or c.get('content_preview', '') or '', 'file_path': c.get('file_path', '')})
        pipe.rpush(QUEUE_KEY, task)
    pipe.execute()

    total += len(chunks)
    min_id = max(c['id'] for c in chunks) + 1

    if total % 50000 == 0 or total < 2000:
        queue_len = r.llen(QUEUE_KEY)
        print(f'  Loaded: {total:,} chunks (queue={queue_len:,}, last_id={min_id-1})')

    # Throttle to avoid overwhelming the API - pause when queue is very large
    queue_len = r.llen(QUEUE_KEY)
    if queue_len > 1000000:
        print(f'  Queue over 1M ({queue_len:,}), pausing 60s...')
        time.sleep(60)
    elif queue_len > 500000:
        time.sleep(0.5)

print(f'Done. Loaded {total:,} total chunks starting from min_id={MIN_ID}')
