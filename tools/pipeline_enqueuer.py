#!/usr/bin/env python3
"""Stage 1: Enqueuer — scans raw scraped files, enqueues via REST API.

Scans /mnt/aio-01/claude-orchestrator/data/scraped/ for files, classifies them
by type (sourcecode/papers/docs), and POSTs file metadata to the orchestrator
queue API (POST /queue/enqueue).

Workers never touch Redis or PostgreSQL directly — everything goes through
the REST API on aio-01:5000.

Usage:
    python3 pipeline_enqueuer.py [--scan-dir /path] [--batch-size 100] [--once]
"""

import argparse
import hashlib
import json
import os
import sys
import time

import requests

SCRAPED_DIR = "/mnt/aio-01/claude-orchestrator/data/scraped"
API_BASE = "http://aio-01:5000"

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

MAX_FILE_SIZE = 1_000_000
MIN_FILE_SIZE = 10


def file_hash(path):
    return hashlib.md5(path.encode()).hexdigest()


def classify_file(subdir):
    return SUBDIR_TYPES.get(subdir, "sourcecode")


def should_skip(path, size):
    if size > MAX_FILE_SIZE or size < MIN_FILE_SIZE:
        return True
    _, ext = os.path.splitext(path)
    return ext.lower() in SKIP_EXTENSIONS


def enqueue_batch(api_base, items):
    """POST batch of items to queue API with retry + backoff."""
    payload = {
        "items": [
            {
                "queue": f"raw_{item['type']}",
                "data": item,
                "priority": 5,
                "idempotency_key": item["file_id"],
            }
            for item in items
        ]
    }
    for attempt in range(4):
        try:
            resp = requests.post(f"{api_base}/queue/enqueue", json=payload, timeout=60)
            resp.raise_for_status()
            result = resp.json()
            return result.get("total_enqueued", 0), result.get("total_duplicates", 0)
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  API error (attempt {attempt+1}/4, retry in {wait}s): {e}", file=sys.stderr)
            time.sleep(wait)
    print(f"  FAILED after 4 attempts, dropping {len(items)} items", file=sys.stderr)
    return 0, 0


def get_queue_status(api_base):
    """GET queue status from API."""
    try:
        resp = requests.get(f"{api_base}/queue/status", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {}


def scan_and_enqueue(api_base, scan_dir, batch_size):
    enqueued = 0
    duplicates = 0
    skipped = 0

    for subdir in sorted(os.listdir(scan_dir)):
        subdir_path = os.path.join(scan_dir, subdir)
        if not os.path.isdir(subdir_path):
            continue

        file_type = classify_file(subdir)
        print(f"  Scanning {subdir} → raw_{file_type}...")
        batch = []

        for root, _dirs, files in os.walk(subdir_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    fsize = os.path.getsize(fpath)
                except OSError:
                    continue

                if should_skip(fpath, fsize):
                    skipped += 1
                    continue

                batch.append({
                    "file_id": file_hash(fpath),
                    "path": fpath,
                    "type": file_type,
                    "subdir": subdir,
                    "size": fsize,
                })

                if len(batch) >= batch_size:
                    added, duped = enqueue_batch(api_base, batch)
                    enqueued += added
                    duplicates += duped
                    batch = []
                    time.sleep(0.1)

        if batch:
            added, duped = enqueue_batch(api_base, batch)
            enqueued += added
            duplicates += duped

    return enqueued, duplicates, skipped


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Enqueue raw scraped files via REST API")
    parser.add_argument("--scan-dir", default=SCRAPED_DIR)
    parser.add_argument("--api-base", default=API_BASE)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--once", action="store_true", help="Run once then exit")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between scans")
    args = parser.parse_args()

    resp = requests.get(f"{args.api_base}/health", timeout=30)
    resp.raise_for_status()
    print(f"API healthy at {args.api_base}")

    while True:
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting scan of {args.scan_dir}")
        enqueued, duplicates, skipped = scan_and_enqueue(args.api_base, args.scan_dir, args.batch_size)
        print(f"  Enqueued: {enqueued}, Duplicates: {duplicates}, Skipped: {skipped}")

        status = get_queue_status(args.api_base)
        if status:
            print(f"  Queue status: {json.dumps(status.get('aggregate', {}), indent=2)}")

        if args.once:
            break

        print(f"  Sleeping {args.interval}s...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
