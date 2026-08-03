#!/usr/bin/env python3
"""Stage 1: Enqueuer — scans raw scraped files and pushes paths onto Redis queues.

Scans /mnt/aio-01/claude-orchestrator/data/scraped/ for files, classifies them
by type (sourcecode/papers/docs), and LPUSH file metadata onto Redis queues.

Only the file path goes into Redis (not content) to keep memory low on 1GB nodes.
Deduplication via Redis SET of already-enqueued file hashes.

Usage:
    python3 pipeline_enqueuer.py [--scan-dir /path] [--batch-size 500] [--max-queue 50000] [--once]
"""

import argparse
import hashlib
import json
import os
import sys
import time

import redis

SCRAPED_DIR = "/mnt/aio-01/claude-orchestrator/data/scraped"

QUEUE_MAP = {
    "sourcecode": "raw:sourcecode",
    "papers": "raw:papers",
    "docs": "raw:docs",
}

SUBDIR_TYPES = {
    "raw-db-languages": "sourcecode",
    "raw-firmware-code": "sourcecode",
    "firmware_code_scraper": "sourcecode",
    "os_code_docs_scraper": "docs",
    "raw-mit-ocw": "docs",
    "mit_ocw_scraper": "docs",
    "wikibooks": "docs",
    "project_gutenberg": "docs",
    "arxiv": "papers",
    "arxiv_scraper_with_storage": "papers",
    "huggingface": "papers",
    "biorxiv": "papers",
    "medrxiv_scraper": "papers",
    "dblp": "papers",
    "acl_anthology": "papers",
    "openreview": "papers",
    "paperswithcode": "papers",
    "google_scholar": "papers",
    "kaggle_notebooks": "docs",
    "leetcode_scraper": "sourcecode",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".exe", ".dll", ".so", ".o", ".a", ".dylib",
    ".pyc", ".pyo", ".class",
    ".woff", ".woff2", ".ttf", ".eot",
}

MAX_FILE_SIZE = 1_000_000  # 1MB — skip huge files
MIN_FILE_SIZE = 10         # skip trivially small files


def get_redis(password=None, host: str = "aio-01", port: int = 6379) -> redis.Redis:
    return redis.Redis(host=host, port=port, password=password, decode_responses=True)


def file_hash(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()


def classify_file(subdir: str) -> str:
    return SUBDIR_TYPES.get(subdir, "sourcecode")


def should_skip(path: str, size: int) -> bool:
    if size > MAX_FILE_SIZE or size < MIN_FILE_SIZE:
        return True
    _, ext = os.path.splitext(path)
    return ext.lower() in SKIP_EXTENSIONS


def scan_and_enqueue(r: redis.Redis, scan_dir: str, batch_size: int, max_queue: int):
    enqueued = 0
    skipped_dup = 0
    skipped_filter = 0
    seen_key = "enqueuer:seen"

    for subdir in sorted(os.listdir(scan_dir)):
        subdir_path = os.path.join(scan_dir, subdir)
        if not os.path.isdir(subdir_path):
            continue

        file_type = classify_file(subdir)
        queue_key = QUEUE_MAP[file_type]

        queue_len = r.llen(queue_key)
        if queue_len >= max_queue:
            print(f"  BACKPRESSURE: {queue_key} has {queue_len} items (max {max_queue}), skipping {subdir}")
            continue

        print(f"  Scanning {subdir} → {queue_key} (type={file_type})...")
        batch = []

        for root, _dirs, files in os.walk(subdir_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    fsize = os.path.getsize(fpath)
                except OSError:
                    continue

                if should_skip(fpath, fsize):
                    skipped_filter += 1
                    continue

                fhash = file_hash(fpath)
                if r.sismember(seen_key, fhash):
                    skipped_dup += 1
                    continue

                item = json.dumps({
                    "file_id": fhash,
                    "path": fpath,
                    "type": file_type,
                    "subdir": subdir,
                    "size": fsize,
                })
                batch.append((fhash, item))

                if len(batch) >= batch_size:
                    pipe = r.pipeline()
                    for h, payload in batch:
                        pipe.lpush(queue_key, payload)
                        pipe.sadd(seen_key, h)
                    pipe.execute()
                    enqueued += len(batch)
                    batch = []

                    queue_len = r.llen(queue_key)
                    if queue_len >= max_queue:
                        print(f"    BACKPRESSURE at {queue_len}, pausing {subdir}")
                        break

            queue_len = r.llen(queue_key)
            if queue_len >= max_queue:
                break

        if batch:
            pipe = r.pipeline()
            for h, payload in batch:
                pipe.lpush(queue_key, payload)
                pipe.sadd(seen_key, h)
            pipe.execute()
            enqueued += len(batch)

    return enqueued, skipped_dup, skipped_filter


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Enqueue raw scraped files to Redis")
    parser.add_argument("--scan-dir", default=SCRAPED_DIR)
    parser.add_argument("--redis-host", default="aio-01")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--redis-password", default=None,
                        help="Redis password (or set REDIS_PASSWORD env var)")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-queue", type=int, default=50000)
    parser.add_argument("--once", action="store_true", help="Run once then exit")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between scans (continuous mode)")
    args = parser.parse_args()

    password = args.redis_password or os.environ.get("REDIS_PASSWORD", "") or None

    r = get_redis(password, args.redis_host, args.redis_port)
    r.ping()
    print(f"Connected to Redis at {args.redis_host}:{args.redis_port}")

    while True:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting scan of {args.scan_dir}")
        enqueued, dup, filtered = scan_and_enqueue(r, args.scan_dir, args.batch_size, args.max_queue)

        for qk in QUEUE_MAP.values():
            print(f"  Queue {qk}: {r.llen(qk)} items")
        print(f"  Enqueued: {enqueued}, Skipped (dup): {dup}, Skipped (filter): {filtered}")
        print(f"  Seen set size: {r.scard('enqueuer:seen')}")

        if args.once:
            break

        print(f"  Sleeping {args.interval}s...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
